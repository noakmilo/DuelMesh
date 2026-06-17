from __future__ import annotations

from .config import BASE_HP, DISPLAY_TARGETS
from .game import DuelState, RoundResult, Target
from .lobby import OpenGame
from .storage import Profile
from .transport import MeshNode


def title(channel: str = "") -> str:
    channel_label = f"Channel: #{channel}" if channel else ""
    return (
        "╔══════════════════════════════════════════════════════════════════════╗\n"
        "║  ██████  ██   ██ ███████ ██     ███   ███ ███████ ███████ ██  ██   ║\n"
        "║  ██   ██ ██   ██ ██      ██     ████ ████ ██      ██      ██  ██   ║\n"
        "║  ██   ██ ██   ██ █████   ██     ██ ███ ██ █████   ███████ ██████   ║\n"
        "║  ██   ██ ██   ██ ██      ██     ██  █  ██ ██           ██ ██  ██   ║\n"
        "║  ██████   █████  ███████ ██████ ██     ██ ███████ ███████ ██  ██   ║\n"
        "║                                                                      ║\n"
        "║                                                                      ║\n"
        "║                O                              O                      ║\n"
        "║               /|\\          ==== VS ====      /|\\                     ║\n"
        "║               / \\                            / \\                     ║\n"
        "║                                                                      ║\n"
        "║                         LoRa Mesh PvP                                ║\n"
        f"║ {channel_label:^68} ║\n"
        "╚══════════════════════════════════════════════════════════════════════╝"
    )


def hp_bar(hp: float, max_hp: float = BASE_HP, width: int = 10) -> str:
    filled = round((max(0.0, hp) / max_hp) * width)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {hp:g}/{max_hp:g}"


def percent_bar(hp: float, max_hp: float = BASE_HP, width: int = 20, reverse: bool = False) -> str:
    percent = max(0, min(100, round((hp / max_hp) * 100)))
    filled = round((percent / 100) * width)
    empty = width - filled
    bar = "█" * filled + "·" * empty
    if reverse:
        bar = "·" * empty + "█" * filled
    return f"[{bar}] {percent:>3}%"


def fight_hud(duel: DuelState, local_is_p1: bool, round_no: int | None = None) -> str:
    local = duel.p1 if local_is_p1 else duel.p2
    enemy = duel.p2 if local_is_p1 else duel.p1
    shown_round = duel.round_no if round_no is None else round_no
    return (
        "╔══════════════════════ DUEL ══════════════════════╗\n"
        f"║ ROUND {shown_round:<3}                         GAME {duel.game_id:<4} ║\n"
        "╠═══════════════════════════════════════════════════╣\n"
        f"║ YOU   {local.nick:<12} {percent_bar(local.hp):<27}║\n"
        f"║ ENEMY {enemy.nick:<12} {percent_bar(enemy.hp, reverse=True):<27}║\n"
        "╚═══════════════════════════════════════════════════╝"
    )


def body_target() -> str:
    return (
        "       [1] HEAD\n"
        "          O\n"
        "       [2] BODY\n"
        "         /|\\\n"
        "       [3] LEGS\n"
        "         / \\"
    )


def lobby_screen(games: list[OpenGame]) -> str:
    lines = [
        "╔══════════════════════════════════════════════════╗",
        "║                    OPEN GAMES                    ║",
        "╠══════════════════════════════════════════════════╣",
    ]
    if not games:
        lines.append("║ No open games heard yet. Use /open or poll.      ║")
    else:
        for index, game in enumerate(games[:12], start=1):
            lines.append(f"║ {index:>2}) {game.game_id:<4} {game.nick:<12} {game.node_id:<12} Waiting ║"[:51] + "║")
    lines.append("╚══════════════════════════════════════════════════╝")
    return "\n".join(lines)


def nodes_screen(nodes: list[MeshNode]) -> str:
    lines = [
        "╔══════════════════════════════════════════════════════╗",
        "║                    MESH NODES                        ║",
        "╠══════════════════════════════════════════════════════╣",
    ]
    if not nodes:
        lines.append("║ No nodes known yet. Wait a moment or send /games.    ║")
    else:
        for index, node in enumerate(nodes[:20], start=1):
            hops = "?" if node.hops_away is None else str(node.hops_away)
            name = node.long_name[:16]
            lines.append(f"║ {index:>2}) {name:<16} {node.node_id:<12} hops {hops:<2} ║"[:55] + "║")
    lines.append("╚══════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def profile_screen(profile: Profile) -> str:
    return (
        f"Nickname: {profile.nickname}\n"
        f"Node ID: {profile.node_id}\n"
        f"Games Played: {profile.games_played}\n"
        f"Wins: {profile.wins}\n"
        f"Losses: {profile.losses}\n"
        f"Draws: {profile.draws}"
    )


def status_screen(duel: DuelState | None, profile: Profile, connection: str, local_is_p1: bool = True) -> str:
    if not duel:
        return f"Nickname: {profile.nickname}\nNode ID: {profile.node_id}\nConnection: {connection}\nNo active duel."
    return (
        f"{fight_hud(duel, local_is_p1)}\n"
        f"Outcome: {duel.outcome}\n"
        f"Connection: {connection}"
    )


def selection_screen(kind: str) -> str:
    if kind == "atk":
        return (
            "Choose ATK:\n\n"
            "1) Head  -2 HP\n"
            "2) Body  -1 HP\n"
            "3) Legs  -0.5 HP\n\n"
            + body_target()
        )
    return "Choose DEF:\n\n1) Head\n2) Body\n3) Legs\n\n" + body_target()


def round_result_screen(
    result: RoundResult,
    p1_name: str,
    p2_name: str,
    duel: DuelState | None = None,
    local_is_p1: bool = True,
) -> str:
    hud = f"{fight_hud(duel, local_is_p1, result.round_no)}\n" if duel else ""
    return (
        hud +
        f"Round {result.round_no} result\n"
        f"{p1_name} took {result.p1_damage:g} damage ({'blocked' if result.p1_blocked else 'hit'})\n"
        f"{p2_name} took {result.p2_damage:g} damage ({'blocked' if result.p2_blocked else 'hit'})\n"
        f"{p1_name}: {hp_bar(result.p1_hp)}\n"
        f"{p2_name}: {hp_bar(result.p2_hp)}"
    )


def victory_screen(outcome: str, local_is_p1: bool) -> str:
    if outcome == "draw":
        word = "DRAW"
    elif (outcome == "p1" and local_is_p1) or (outcome == "p2" and not local_is_p1):
        word = "VICTORY"
    else:
        word = "DEFEAT"
    return f"╔══════════════╗\n║ {word:^12} ║\n╚══════════════╝"


def waiting_screen(what: str) -> str:
    return f"Waiting for {what}..."


def target_from_menu(value: str) -> Target:
    mapping = {"1": "head", "2": "body", "3": "legs"}
    if value not in mapping:
        raise ValueError("Choose 1, 2, or 3")
    return mapping[value]  # type: ignore[return-value]


def target_label(target: Target) -> str:
    return DISPLAY_TARGETS[target]
