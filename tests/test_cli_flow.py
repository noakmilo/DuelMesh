import pytest
from argparse import Namespace

from duelmesh.cli import PendingTurn, Session, build_transport, prompt_startup, run_command
from duelmesh.game import DuelState, PlayerState, TurnChoice, rules_hash, turn_commit
from duelmesh.lobby import Lobby
from duelmesh.protocol import Packet, reveal_payload
from duelmesh.storage import Profile
from duelmesh.transport import MockTransport


def make_session(node: str, nick: str, tmp_path) -> Session:
    transport = MockTransport(node, tmp_path)
    profile = Profile(nick, node)
    return Session(profile, transport, Lobby(transport, node, nick))


def pair_sessions(host: Session, guest: Session) -> None:
    game_id = host.lobby.open_game("ABCD")
    host.open_game_id = game_id
    guest.lobby.list_games()
    guest.join(game_id)
    host.poll()
    guest.poll()


def test_guest_cannot_duel_before_initiative_player_commits(tmp_path) -> None:
    host = make_session("!a", "Alice", tmp_path)
    guest = make_session("!b", "Bob", tmp_path)
    pair_sessions(host, guest)
    host.local_roll = 6
    host.remote_roll = 1
    guest.local_roll = 1
    guest.remote_roll = 6
    host._try_set_initiative()
    guest._try_set_initiative()

    with pytest.raises(ValueError, match="not your turn"):
        guest.commit_turn(TurnChoice("head", "body", "s2"))

    host.commit_turn(TurnChoice("body", "head", "s1"))
    guest.poll()
    assert guest.pending is not None
    assert guest.pending.remote_commit is not None
    assert guest.needs_turn_prompt()


def test_shutdown_forfeits_active_duel(tmp_path) -> None:
    host = make_session("!a", "Alice", tmp_path)
    guest = make_session("!b", "Bob", tmp_path)
    pair_sessions(host, guest)

    host.shutdown()
    guest.poll()

    assert guest.profile.wins == 1
    assert guest.duel is None


def test_join_closes_existing_open_game(tmp_path) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    bob = make_session("!b", "Bob", tmp_path)
    carol = make_session("!c", "Carol", tmp_path)

    alice.open_game_id = alice.lobby.open_game("AAAA")
    bob.open_game_id = bob.lobby.open_game("BBBB")
    alice.lobby.list_games()

    assert alice.open_game_id == "AAAA"
    assert "BBBB" in {game.game_id for game in alice.lobby.list_games()}

    alice.join("BBBB")
    carol.lobby.list_games()

    assert alice.open_game_id is None
    assert "AAAA" not in {game.game_id for game in carol.lobby.list_games()}


def test_join_accepts_numbered_game_selection(tmp_path) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    bob = make_session("!b", "Bob", tmp_path)

    alice.open_game_id = alice.lobby.open_game("AAAA")
    bob.lobby.list_games()

    message = bob.join("1")

    assert message == "Join request sent to Alice."
    assert bob.duel is not None
    assert bob.duel.game_id == "AAAA"


def test_finished_duel_clears_session_and_shows_main_menu(tmp_path, capsys) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    alice.opponent_node = "!b"
    alice.local_is_p1 = True
    alice.initiative_node = "!a"
    alice.previous_initiative_node = "!a"
    alice.duel = DuelState(
        "DONE",
        PlayerState("!a", "Alice", hp=10),
        PlayerState("!b", "Bob", hp=2),
    )
    alice.pending = None

    alice.commit_turn(TurnChoice("head", "head", "s1"))
    assert alice.pending is not None
    alice.pending.remote_commit = "remote"
    alice.pending.remote_reveal = TurnChoice("body", "body", "s2")
    alice.pending.revealed = True

    alice._try_resolve()

    assert alice.duel is None
    assert alice.pending is None
    assert not alice.needs_turn_prompt()
    out = capsys.readouterr().out
    assert "LoRa Mesh PvP" in out
    assert "Channel: #mock" in out
    assert "/open" in out


def test_roll_message_when_opponent_already_won(tmp_path, monkeypatch) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    alchemist = make_session("!b", "Alchemist", tmp_path)
    pair_sessions(alice, alchemist)
    alchemist.remote_roll = 6
    monkeypatch.setattr("duelmesh.cli.secrets.randbelow", lambda sides: 0)

    message = alchemist.roll_d6()

    assert "Prepare yourself" in message
    assert "Alice is choosing ATK/DEF" in message
    assert "Waiting for opponent roll" not in message


def test_nodes_command_lists_known_mock_nodes(tmp_path, capsys) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    bob = make_session("!b", "Bob", tmp_path)
    alice.lobby.open_game("AAAA")
    bob.lobby.list_games()

    run_command(bob, "/nodes")

    out = capsys.readouterr().out
    assert "MESH NODES" in out
    assert "Alice" in out
    assert "1)" in out


def test_credits_command(tmp_path, capsys) -> None:
    alice = make_session("!a", "Alice", tmp_path)

    run_command(alice, "/credits")

    out = capsys.readouterr().out
    assert "u/noakmilo" in out
    assert "ChatGPT Codex" in out


def test_clear_history_clears_lobby_cache_and_mock_bus(tmp_path) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    bob = make_session("!b", "Bob", tmp_path)
    alice.lobby.open_game("AAAA")
    bob.lobby.list_games()
    assert bob.lobby.games
    assert bob.transport.bus.read_text(encoding="utf-8")

    message = bob.clear_history()

    assert message == "Local DuelMesh message history cleared."
    assert not bob.lobby.games
    assert not bob.seen_packets
    assert bob.transport.bus.read_text(encoding="utf-8") == ""


def test_clear_history_blocked_during_active_duel(tmp_path) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    bob = make_session("!b", "Bob", tmp_path)
    pair_sessions(alice, bob)

    with pytest.raises(ValueError, match="active duel"):
        bob.clear_history()


def test_clear_history_blocked_with_open_game(tmp_path) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    alice.open_game_id = alice.lobby.open_game("AAAA")

    with pytest.raises(ValueError, match="open game"):
        alice.clear_history()


def test_pending_reveal_is_resent(tmp_path, monkeypatch) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    bob = make_session("!b", "Bob", tmp_path)
    pair_sessions(alice, bob)
    alice.duel = DuelState("ABCD", PlayerState("!a", "Alice"), PlayerState("!b", "Bob"))
    alice.opponent_node = "!b"
    alice.pending = alice.pending or None
    alice.initiative_node = "!a"

    alice.commit_turn(TurnChoice("head", "body", "s1"))
    alice.pending.remote_commit = "remote"
    alice.reveal()
    first_reveal_at = alice.pending.last_reveal_at
    monkeypatch.setattr("duelmesh.cli.time.time", lambda: first_reveal_at + 25)

    alice.resend_pending()

    assert alice.pending.last_reveal_at > first_reveal_at


def test_duplicate_remote_commit_is_ignored_after_reveal(tmp_path, capsys) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    alice.duel = DuelState("ABCD", PlayerState("!a", "Alice"), PlayerState("!b", "Bob"))
    alice.opponent_node = "!b"
    alice.initiative_node = "!a"
    alice.commit_turn(TurnChoice("head", "body", "s1"))
    assert alice.pending is not None
    commit = "same"
    duplicate = Packet(
        t="commit",
        g="ABCD",
        s="!b",
        n="Bob",
        d={"r": 1, "c": commit, "rh": rules_hash()},
    )

    alice._handle_commit(duplicate)
    first_reveal_count = alice.pending.reveal_send_count
    capsys.readouterr()
    alice._handle_commit(duplicate)

    out = capsys.readouterr().out
    assert "Revealing result" not in out
    assert alice.pending.reveal_send_count == first_reveal_count


def test_completed_round_reveal_is_resent_for_waiting_peer(tmp_path) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    bob = make_session("!b", "Bob", tmp_path)
    bob.duel = DuelState("ABCD", PlayerState("!a", "Alice"), PlayerState("!b", "Bob"))
    bob.opponent_node = "!a"
    bob.local_is_p1 = False
    alice_turn = TurnChoice("head", "body", "s1")
    bob_turn = TurnChoice("body", "legs", "s2")
    bob.duel.apply_round(alice_turn, bob_turn)
    stale_reveal = Packet(
        t="reveal",
        g="ABCD",
        s="!a",
        n="Alice",
        d=reveal_payload(1, alice_turn.atk, alice_turn.defense, alice_turn.salt),
    )

    bob._handle_reveal(stale_reveal)

    packets = alice.transport.receive()
    assert [packet.t for packet in packets] == ["reveal"]
    assert packets[0].d == reveal_payload(1, bob_turn.atk, bob_turn.defense, bob_turn.salt)


def test_resolving_round_sends_completed_reveal_once(tmp_path) -> None:
    alice = make_session("!a", "Alice", tmp_path)
    bob = make_session("!b", "Bob", tmp_path)
    pair_sessions(alice, bob)
    bob.local_is_p1 = False
    bob.opponent_node = "!a"
    bob.initiative_node = "!a"
    bob.previous_initiative_node = "!a"
    bob.duel = DuelState("ABCD", PlayerState("!a", "Alice"), PlayerState("!b", "Bob"))
    bob.pending = None
    bob.pending = bob.pending or None

    bob.pending = PendingTurn(1)
    bob.pending.choice = TurnChoice("body", "legs", "s2")
    bob.pending.local_commit = "local"
    bob.pending.remote_commit = turn_commit(1, "head", "body", "s1")
    bob.pending.remote_reveal = TurnChoice("head", "body", "s1")
    bob.pending.revealed = True

    bob._try_resolve()

    packets = alice.transport.receive()
    assert packets[-1].t == "reveal"
    assert packets[-1].d == reveal_payload(1, "body", "legs", "s2")


def test_startup_prompt_selects_ble_and_profile_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DUELMESH_HOME", "")
    monkeypatch.setattr("duelmesh.cli.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("duelmesh.cli.ble_devices", lambda: [("Meshtastic_c95c", "AA:BB")])
    answers = iter(["1", "1", "Bob"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    args = prompt_startup(
        Namespace(
            transport=None,
            nick=None,
            port=None,
            ble=None,
            data_dir=None,
            mock_dir=None,
        )
    )

    assert args.transport == "lora"
    assert args.ble == "Meshtastic_c95c"
    assert args.port is None
    assert args.nick == "Bob"


def test_startup_prompt_selects_usb_port(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DUELMESH_HOME", "")
    monkeypatch.setattr("duelmesh.cli.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("duelmesh.cli.serial_ports", lambda: ["/dev/cu.HELTEC"])
    monkeypatch.setattr("duelmesh.cli.meshtastic_long_name", lambda: None)
    answers = iter(["2", "1", "Alice"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    args = prompt_startup(
        Namespace(
            transport=None,
            nick=None,
            port=None,
            ble=None,
            data_dir=None,
            mock_dir=None,
        )
    )

    assert args.transport == "lora"
    assert args.port == "/dev/cu.HELTEC"
    assert args.ble is None
    assert args.nick == "Alice"


def test_lora_rejects_primary_channel() -> None:
    with pytest.raises(ValueError, match="dedicated Meshtastic channel"):
        build_transport("lora", Profile("Alice", "!a"), channel_index=0)
