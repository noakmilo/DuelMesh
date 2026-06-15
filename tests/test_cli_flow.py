import pytest

from duelmesh.cli import Session
from duelmesh.game import DuelState, PlayerState, TurnChoice
from duelmesh.lobby import Lobby
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


def test_finished_duel_clears_session_and_stops_turn_prompt(tmp_path) -> None:
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
