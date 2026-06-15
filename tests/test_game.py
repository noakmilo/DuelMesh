from duelmesh.game import DuelState, PlayerState, TurnChoice, replay


def test_round_resolution_and_replay() -> None:
    duel = DuelState("ABCD", PlayerState("!a", "Alice"), PlayerState("!b", "Bob"))
    result = duel.apply_round(TurnChoice("head", "body", "s1"), TurnChoice("body", "legs", "s2"))

    assert result.p1_damage == 0
    assert result.p2_damage == 2
    assert duel.p1.hp == 10
    assert duel.p2.hp == 8
    assert replay(duel) == "active"


def test_draw_when_both_reach_zero_same_round() -> None:
    duel = DuelState("ABCD", PlayerState("!a", "Alice", hp=1), PlayerState("!b", "Bob", hp=1))
    result = duel.apply_round(TurnChoice("body", "legs", "s1"), TurnChoice("body", "legs", "s2"))

    assert result.outcome == "draw"

