from duelmesh.ascii_ui import fight_hud, hp_bar, percent_bar, target_from_menu
from duelmesh.game import DuelState, PlayerState


def test_hp_bar() -> None:
    assert hp_bar(5).startswith("[#####-----]")


def test_percent_bar() -> None:
    assert percent_bar(5, width=10) == "[█████·····]  50%"


def test_fight_hud_shows_you_and_enemy_percentages() -> None:
    duel = DuelState("ABCD", PlayerState("!a", "Alice", hp=10), PlayerState("!b", "Bob", hp=7.5))

    hud = fight_hud(duel, local_is_p1=True)

    assert "YOU" in hud
    assert "ENEMY" in hud
    assert "100%" in hud
    assert "75%" in hud


def test_target_from_menu() -> None:
    assert target_from_menu("1") == "head"
    assert target_from_menu("2") == "body"
    assert target_from_menu("3") == "legs"
