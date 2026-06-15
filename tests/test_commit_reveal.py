from duelmesh.game import TurnChoice, turn_commit


def test_commit_reveal_verifies_exact_turn() -> None:
    choice = TurnChoice("head", "body", "abc")
    commit = turn_commit(3, choice.atk, choice.defense, choice.salt)

    assert commit == turn_commit(3, "head", "body", "abc")
    assert commit != turn_commit(3, "legs", "body", "abc")
    assert commit != turn_commit(4, "head", "body", "abc")

