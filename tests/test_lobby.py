from duelmesh.game import rules_hash
from duelmesh.lobby import Lobby
from duelmesh.transport import MockTransport


def test_lobby_discovers_open_games(tmp_path) -> None:
    ta = MockTransport("!a", tmp_path)
    tb = MockTransport("!b", tmp_path)
    la = Lobby(ta, "!a", "Alice")
    lb = Lobby(tb, "!b", "Bob")

    game_id = la.open_game("K7Q4")
    games = lb.list_games()

    assert game_id == "K7Q4"
    assert len(games) == 1
    assert games[0].nick == "Alice"
    assert games[0].rules_hash == rules_hash()


def test_two_hosts_see_each_others_open_games(tmp_path) -> None:
    ta = MockTransport("!a", tmp_path)
    tb = MockTransport("!b", tmp_path)
    la = Lobby(ta, "!a", "Alice")
    lb = Lobby(tb, "!b", "Bob")

    la.open_game("AAAA")
    lb.open_game("BBBB")

    alice_games = la.list_games()
    bob_games = lb.list_games()

    assert [game.game_id for game in alice_games] == ["BBBB"]
    assert [game.game_id for game in bob_games] == ["AAAA"]


def test_lobby_removes_cancelled_games(tmp_path) -> None:
    ta = MockTransport("!a", tmp_path)
    tb = MockTransport("!b", tmp_path)
    la = Lobby(ta, "!a", "Alice")
    lb = Lobby(tb, "!b", "Bob")

    game_id = la.open_game("K7Q4")
    assert len(lb.list_games()) == 1
    la.cancel(game_id)

    assert lb.list_games() == []
