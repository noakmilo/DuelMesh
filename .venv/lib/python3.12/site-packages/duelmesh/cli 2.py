from __future__ import annotations

import argparse
import os
import secrets
import select
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import ascii_ui
from .game import DuelState, PlayerState, TurnChoice, replay, rules_hash, turn_commit
from .lobby import Lobby
from .node_setup import meshtastic_long_name
from .protocol import ProtocolError, build_packet, commit_payload, reveal_payload
from .storage import Profile, ensure_profile, load_profile, save_profile, update_nick
from .transport import MeshtasticTransport, MockTransport, Transport


HELP = """Commands:
/open              Create public duel offer
/games             List open games
/join GAME_ID      Join an open game
/status            Show profile, HP, round, and connection
/roll              Roll a d6 for first initiative
/reveal            Send your current turn reveal or final proof
/cancel            Cancel open or active duel
/nick NEWNAME      Change nickname
/profile           Show local profile
/help              Show commands
/quit              Save and exit
"""


@dataclass
class PendingTurn:
    round_no: int
    choice: TurnChoice | None = None
    local_commit: str | None = None
    remote_commit: str | None = None
    remote_reveal: TurnChoice | None = None
    revealed: bool = False


@dataclass
class Session:
    profile: Profile
    transport: Transport
    lobby: Lobby
    duel: DuelState | None = None
    opponent_node: str | None = None
    local_is_p1: bool = True
    open_game_id: str | None = None
    pending: PendingTurn | None = None
    initiative_node: str | None = None
    previous_initiative_node: str | None = None
    local_roll: int | None = None
    remote_roll: int | None = None
    last_offer_at: float = 0.0
    closed: bool = False
    seen_packets: set[tuple[str, str, str, str]] = field(default_factory=set)

    def poll(self) -> None:
        for packet in self.lobby.poll():
            key = (packet.t, packet.g, packet.s, packet.m)
            if key in self.seen_packets:
                continue
            self.seen_packets.add(key)
            if packet.t == "join" and self.open_game_id == packet.g:
                data = packet.d or {}
                if data.get("rh") != rules_hash():
                    print("Rules mismatch. Duel cancelled.")
                    self.lobby.cancel(packet.g, packet.s)
                    continue
                self.opponent_node = packet.s
                self.local_is_p1 = True
                self.duel = DuelState(packet.g, PlayerState(self.profile.node_id, self.profile.nickname), PlayerState(packet.s, packet.n))
                accept = build_packet("accept", packet.g, self.profile.node_id, self.profile.nickname, rh=rules_hash())
                self.transport.send_direct(packet.s, accept)
                self.lobby.close_offer(packet.g)
                self.open_game_id = None
                print(f"\n{packet.n} joined your game. Both players must use /roll.")
            elif packet.t == "accept" and self.duel and packet.g == self.duel.game_id:
                print(f"\n{packet.n} accepted. Both players must use /roll.")
            elif packet.t == "cancel" and self.duel and packet.g == self.duel.game_id:
                print("Duel cancelled by opponent.")
                self.duel = None
                self.pending = None
                self.initiative_node = None
            elif packet.t == "forfeit" and self.duel and packet.g == self.duel.game_id:
                self._finish_by_forfeit(packet.n)
            elif packet.t == "commit" and self.duel and packet.g == self.duel.game_id:
                self._handle_commit(packet)
            elif packet.t == "reveal" and self.duel and packet.g == self.duel.game_id:
                self._handle_reveal(packet)
            elif packet.t == "roll" and self.duel and packet.g == self.duel.game_id:
                self._handle_roll(packet)

    def join(self, game_id: str) -> str:
        games = {g.game_id: g for g in self.lobby.list_games()}
        if game_id not in games:
            raise ValueError("Game not found. Use /games first.")
        game = games[game_id]
        if game.rules_hash != rules_hash():
            raise ValueError("Rules mismatch. Duel cancelled.")
        if self.open_game_id:
            self.lobby.close_offer(self.open_game_id)
            self.open_game_id = None
        self.lobby.join_game(game)
        self.opponent_node = game.node_id
        self.local_is_p1 = False
        self.duel = DuelState(game.game_id, PlayerState(game.node_id, game.nick), PlayerState(self.profile.node_id, self.profile.nickname))
        return f"Join request sent to {game.nick}."

    def roll_d6(self) -> str:
        if not self.duel or not self.opponent_node:
            raise ValueError("No active duel.")
        if self.initiative_node is not None:
            raise ValueError("Initiative is already decided.")
        if self.local_roll is not None and self.remote_roll is None:
            raise ValueError("You already rolled. Waiting for opponent roll.")
        self.local_roll = secrets.randbelow(6) + 1
        packet = build_packet("roll", self.duel.game_id, self.profile.node_id, self.profile.nickname, r=self.local_roll)
        self.transport.send_direct(self.opponent_node, packet)
        rolled = self.local_roll
        self._try_set_initiative()
        if self.local_roll is None and self.remote_roll is None:
            return f"You rolled {rolled}. Dice draw."
        if self.initiative_node == self.profile.node_id:
            return f"You rolled {rolled}. You have initiative."
        if self.initiative_node == self.opponent_node:
            return f"You rolled {rolled}. Prepare yourself. {self._opponent_name()} is choosing ATK/DEF."
        return f"You rolled {rolled}. Waiting for opponent roll."

    def commit_turn(self, choice: TurnChoice) -> str:
        if not self.duel or not self.opponent_node:
            raise ValueError("No active duel.")
        if self.duel.outcome != "active":
            raise ValueError("Duel is already finished.")
        if self.initiative_node is None:
            raise ValueError("Roll first with /roll.")
        if self.pending and self.pending.choice:
            raise ValueError("You already played this round.")
        if self.initiative_node != self.profile.node_id:
            if not self.pending or not self.pending.remote_commit:
                raise ValueError("It is not your turn yet.")
        commit = turn_commit(self.duel.round_no, choice.atk, choice.defense, choice.salt)
        if not self.pending or self.pending.round_no != self.duel.round_no:
            self.pending = PendingTurn(self.duel.round_no)
        self.pending.choice = choice
        self.pending.local_commit = commit
        packet = build_packet(
            "commit",
            self.duel.game_id,
            self.profile.node_id,
            self.profile.nickname,
            **commit_payload(self.duel.round_no, commit),
        )
        self.transport.send_direct(self.opponent_node, packet)
        if self.pending.remote_commit:
            self.reveal()
        return "Turn committed."

    def reveal(self) -> str:
        if not self.pending or not self.pending.choice or not self.duel or not self.opponent_node:
            return "Nothing to reveal."
        if self.duel.outcome != "active":
            return "Duel is already finished."
        packet = build_packet(
            "reveal",
            self.duel.game_id,
            self.profile.node_id,
            self.profile.nickname,
            **reveal_payload(self.pending.round_no, self.pending.choice.atk, self.pending.choice.defense, self.pending.choice.salt),
        )
        self.transport.send_direct(self.opponent_node, packet)
        self.pending.revealed = True
        self._try_resolve()
        return "Reveal sent."

    def _handle_roll(self, packet) -> None:
        data = packet.d or {}
        self.remote_roll = int(data["r"])
        print(f"\n{packet.n} rolled {self.remote_roll}.")
        self._try_set_initiative()

    def _try_set_initiative(self) -> None:
        if not self.duel or self.local_roll is None or self.remote_roll is None:
            return
        if self.local_roll == self.remote_roll:
            self.local_roll = None
            self.remote_roll = None
            print("Dice draw. Both players roll again with /roll.")
            return
        self.initiative_node = self.profile.node_id if self.local_roll > self.remote_roll else self.opponent_node
        self.previous_initiative_node = self.initiative_node
        who = "You start" if self.initiative_node == self.profile.node_id else f"{self._opponent_name()} starts"
        print(f"Initiative: {who}.")
        if self.initiative_node == self.profile.node_id:
            print("Your turn.")
        else:
            print(f"Prepare yourself. {self._opponent_name()} is choosing ATK/DEF.")

    def _handle_commit(self, packet) -> None:
        if not self.duel or self.duel.outcome != "active":
            return
        data = packet.d or {}
        if data.get("rh") != rules_hash():
            print("Rules mismatch. Duel cancelled.")
            self.lobby.cancel(packet.g, packet.s)
            self.duel = None
            return
        if int(data.get("r", 0)) != self.duel.round_no:
            return
        if not self.pending or self.pending.round_no != self.duel.round_no:
            self.pending = PendingTurn(self.duel.round_no)
        self.pending.remote_commit = data.get("c")
        if self.pending.choice:
            print(f"\n{packet.n} also played round {self.duel.round_no}. Revealing result.")
            self.reveal()
        else:
            print(f"\n{packet.n} already played round {self.duel.round_no}. Your turn.")
            print(ascii_ui.waiting_screen("your turn selection"))

    def _handle_reveal(self, packet) -> None:
        if not self.duel or self.duel.outcome != "active":
            return
        if not self.pending or not self.pending.choice:
            print("Received reveal before local commit; ignored.")
            return
        data = packet.d or {}
        remote = TurnChoice(data["atk"], data["def"], data["salt"])
        expected = self.pending.remote_commit
        actual = turn_commit(int(data["r"]), remote.atk, remote.defense, remote.salt)
        if expected and expected != actual:
            print("CHEATING OR CLIENT MISMATCH DETECTED")
            return
        self.pending.remote_reveal = remote
        self._try_resolve()

    def _try_resolve(self) -> None:
        if not self.duel or not self.pending or not self.pending.remote_reveal or not self.pending.revealed:
            return
        if self.local_is_p1:
            result = self.duel.apply_round(self.pending.choice, self.pending.remote_reveal)
        else:
            result = self.duel.apply_round(self.pending.remote_reveal, self.pending.choice)
        print(ascii_ui.round_result_screen(result, self.duel.p1.nick, self.duel.p2.nick, self.duel, self.local_is_p1))
        self._set_next_initiative(result.p1_damage, result.p2_damage)
        self.pending = None
        if result.outcome != "active":
            self._finish(result.outcome)
        elif self.initiative_node == self.profile.node_id:
            print("You won initiative for the next round.")
        else:
            print(ascii_ui.waiting_screen(f"{self._opponent_name()} turn"))

    def _set_next_initiative(self, p1_damage: float, p2_damage: float) -> None:
        if not self.duel:
            return
        if p1_damage == p2_damage:
            self.initiative_node = self.previous_initiative_node
        elif p1_damage < p2_damage:
            self.initiative_node = self.duel.p1.node_id
        else:
            self.initiative_node = self.duel.p2.node_id
        self.previous_initiative_node = self.initiative_node

    def _opponent_name(self) -> str:
        if not self.duel:
            return "opponent"
        return self.duel.p2.nick if self.local_is_p1 else self.duel.p1.nick

    def needs_turn_prompt(self) -> bool:
        if not self.duel or self.duel.outcome != "active":
            return False
        if self.pending and self.pending.choice:
            return False
        if self.pending and self.pending.remote_commit:
            return True
        return self.initiative_node == self.profile.node_id and self.pending is None

    def heartbeat_offer(self) -> None:
        if not self.open_game_id or self.duel:
            return
        now = time.time()
        if now - self.last_offer_at >= 8:
            self.lobby.open_game(self.open_game_id)
            self.last_offer_at = now

    def shutdown(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.duel and self.opponent_node and self.duel.outcome == "active":
            packet = build_packet("forfeit", self.duel.game_id, self.profile.node_id, self.profile.nickname)
            self.transport.send_direct(self.opponent_node, packet)
        elif self.open_game_id:
            self.lobby.cancel(self.open_game_id)
        save_profile(self.profile)

    def _finish_by_forfeit(self, opponent_nick: str) -> None:
        print(f"\n{opponent_nick} surrendered. You win.")
        print(ascii_ui.victory_screen("p1" if self.local_is_p1 else "p2", self.local_is_p1))
        self.profile.games_played += 1
        self.profile.wins += 1
        save_profile(self.profile)
        self.duel = None
        self.pending = None
        self.initiative_node = None
        self.previous_initiative_node = None

    def _finish(self, outcome: str) -> None:
        assert self.duel
        print(ascii_ui.victory_screen(outcome, self.local_is_p1))
        if replay(self.duel) != outcome:
            print("CHEATING OR CLIENT MISMATCH DETECTED")
        self.profile.games_played += 1
        if outcome == "draw":
            self.profile.draws += 1
        elif (outcome == "p1" and self.local_is_p1) or (outcome == "p2" and not self.local_is_p1):
            self.profile.wins += 1
        else:
            self.profile.losses += 1
        save_profile(self.profile)
        self.duel = None
        self.pending = None
        self.initiative_node = None
        self.previous_initiative_node = None
        self.local_roll = None
        self.remote_roll = None


def choose_turn() -> TurnChoice:
    print(ascii_ui.selection_screen("atk"))
    atk = ascii_ui.target_from_menu(input("ATK? ").strip())
    print(ascii_ui.selection_screen("def"))
    defense = ascii_ui.target_from_menu(input("DEF? ").strip())
    print(f"You selected:\n\nATK: {ascii_ui.target_label(atk)}\nDEF: {ascii_ui.target_label(defense)}\n")
    if input("Lock turn? y/n ").strip().lower() != "y":
        raise ValueError("Turn cancelled.")
    return TurnChoice(atk, defense)


def confirm_join_closes_offer(open_game_id: str | None) -> bool:
    if not open_game_id:
        return True
    print(
        f"You currently have open game {open_game_id}. "
        "Joining another game will remove your open game from the mesh lobby."
    )
    return input("Continue? y/n ").strip().lower() == "y"


def get_or_create_profile(args: argparse.Namespace) -> Profile:
    profile = load_profile()
    if profile:
        return profile
    default_nick = args.nick or meshtastic_long_name()
    while not default_nick:
        default_nick = input("Choose nickname: ").strip()
    return ensure_profile(default_nick)


def build_transport(
    kind: str,
    profile: Profile,
    mock_dir: str | None = None,
    port: str | None = None,
    ble: str | None = None,
) -> Transport:
    if kind == "lora":
        return MeshtasticTransport(port=port, ble=ble)
    shared_mock_dir = Path.cwd() / ".duelmesh" / "mockmesh"
    return MockTransport(profile.node_id, shared_mock_dir if mock_dir is None else Path(mock_dir))


def configure_data_dir(args: argparse.Namespace) -> None:
    if args.data_dir:
        os.environ["DUELMESH_HOME"] = args.data_dir
        return
    if args.transport == "mock" and args.nick:
        os.environ["DUELMESH_HOME"] = str(Path.cwd() / ".duelmesh" / args.nick)


def run_command(session: Session, command: str) -> bool:
    session.poll()
    parts = command.strip().split()
    if not parts:
        return True
    cmd = parts[0].lower()
    try:
        if cmd == "/open":
            game_id = session.lobby.open_game()
            session.open_game_id = game_id
            print(f"Open game {game_id}.")
        elif cmd == "/games":
            print(ascii_ui.lobby_screen(session.lobby.list_games()))
        elif cmd == "/join":
            if len(parts) != 2:
                print("Usage: /join GAME_ID")
            elif not confirm_join_closes_offer(session.open_game_id):
                print("Join cancelled.")
            else:
                print(session.join(parts[1].upper()))
        elif cmd == "/status":
            print(ascii_ui.status_screen(session.duel, session.profile, type(session.transport).__name__, session.local_is_p1))
        elif cmd == "/roll":
            print(session.roll_d6())
        elif cmd == "/reveal":
            print(session.reveal())
        elif cmd == "/cancel":
            if session.duel and session.opponent_node:
                session.lobby.cancel(session.duel.game_id, session.opponent_node)
            elif session.open_game_id:
                session.lobby.cancel(session.open_game_id)
            session.duel = None
            session.pending = None
            print("Cancelled.")
        elif cmd == "/nick":
            if len(parts) != 2:
                print("Usage: /nick NEWNAME")
            else:
                update_nick(session.profile, parts[1])
                session.lobby.nick = session.profile.nickname
                print(f"Nickname changed to {session.profile.nickname}.")
        elif cmd == "/profile":
            print(ascii_ui.profile_screen(session.profile))
        elif cmd == "/help":
            print(HELP)
        elif cmd == "/quit":
            session.shutdown()
            return False
        else:
            print("Unknown command. Use /help.")
    except (ValueError, ProtocolError, KeyError) as exc:
        print(exc)
    session.poll()
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DuelMesh ASCII duel over mock mesh or Meshtastic LoRa")
    parser.add_argument("--transport", choices=["mock", "lora"], default="mock")
    parser.add_argument("--nick", help="Nickname for first launch")
    parser.add_argument("--port", help="Serial port for Meshtastic hardware, e.g. /dev/cu.usbserial-0001.")
    parser.add_argument("--ble", help="Bluetooth LE address or device name for Meshtastic hardware.")
    parser.add_argument("--data-dir", help="Profile/state directory. Useful for running two local players.")
    parser.add_argument("--mock-dir", help="Shared mock mesh directory. Defaults to .duelmesh/mockmesh.")
    args = parser.parse_args(argv)

    try:
        configure_data_dir(args)
        profile = get_or_create_profile(args)
        if args.transport == "lora" and args.port and args.ble:
            raise ValueError("Use either --port or --ble, not both.")
        transport = build_transport(args.transport, profile, args.mock_dir, args.port, args.ble)
        if args.transport == "lora" and profile.node_id != transport.node_id:
            profile.node_id = transport.node_id
            save_profile(profile)
    except Exception as exc:
        print(f"Startup error: {exc}", file=sys.stderr)
        return 1

    lobby = Lobby(transport, profile.node_id, profile.nickname)
    session = Session(profile, transport, lobby)
    print(ascii_ui.title())
    print(HELP)
    prompt_visible = False
    try:
        while True:
            session.poll()
            session.heartbeat_offer()
            if session.needs_turn_prompt():
                if prompt_visible:
                    print()
                    prompt_visible = False
                try:
                    print(session.commit_turn(choose_turn()))
                except (ValueError, ProtocolError, KeyError) as exc:
                    print(exc)
                continue
            if not prompt_visible:
                print("duelmesh> ", end="", flush=True)
                prompt_visible = True
            ready, _, _ = select.select([sys.stdin], [], [], 0.25)
            if not ready:
                continue
            command = sys.stdin.readline()
            if command == "":
                print()
                break
            prompt_visible = False
            if not run_command(session, command):
                break
            time.sleep(0.05)
    finally:
        session.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
