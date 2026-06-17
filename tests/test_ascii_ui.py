from duelmesh.ascii_ui import credits_screen, fight_hud, hp_bar, percent_bar, target_from_menu, title
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


def test_title_shows_channel() -> None:
    banner = title("DuelMesh")
    assert "Channel: #DuelMesh" in banner
    assert "by u/noakmilo + Codex" in banner


def test_credits_screen() -> None:
    credits = credits_screen()
    assert "u/noakmilo" in credits
    assert "ChatGPT Codex" in credits
    assert "Meshtastic" in credits
