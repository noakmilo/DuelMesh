from __future__ import annotations

import secrets
import string
import time
from dataclasses import dataclass

from .game import RULESET_ID, rules_hash
from .protocol import Packet, build_packet, offer_packet
from .transport import Transport, dedupe_packets


GAME_TTL_SECONDS = 20


def make_game_id() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(4))


@dataclass
class OpenGame:
    game_id: str
    nick: str
    node_id: str
    seen_at: float
    rules: str
    rules_hash: str


class Lobby:
    def __init__(self, transport: Transport, node_id: str, nick: str) -> None:
        self.transport = transport
        self.node_id = node_id
        self.nick = nick
        self.games: dict[str, OpenGame] = {}
        self.last_poll = 0.0

    def open_game(self, game_id: str | None = None) -> str:
        game_id = game_id or make_game_id()
        self.transport.send_public(offer_packet(game_id, self.node_id, self.nick))
        return game_id

    def join_game(self, game: OpenGame) -> None:
        packet = build_packet(
            "join",
            game.game_id,
            self.node_id,
            self.nick,
            rules=RULESET_ID,
            rh=rules_hash(),
        )
        self.transport.send_direct(game.node_id, packet)

    def cancel(self, game_id: str, dest_node: str | None = None) -> None:
        packet = build_packet("cancel", game_id, self.node_id, self.nick)
        if dest_node:
            self.transport.send_direct(dest_node, packet)
        else:
            self.transport.send_public(packet)

    def close_offer(self, game_id: str) -> None:
        self.transport.send_public(build_packet("close", game_id, self.node_id, self.nick))

    def poll(self) -> list[Packet]:
        now = time.time()
        packets = dedupe_packets(self.transport.receive(self.last_poll))
        self.last_poll = now
        for packet in packets:
            if packet.t == "offer" and packet.s != self.node_id:
                data = packet.d or {}
                self.games[packet.g] = OpenGame(
                    game_id=packet.g,
                    nick=packet.n,
                    node_id=packet.s,
                    seen_at=packet.ts,
                    rules=data.get("rules", ""),
                    rules_hash=data.get("rh", ""),
                )
            if packet.t in {"cancel", "close"} and packet.g in self.games:
                del self.games[packet.g]
        return packets

    def list_games(self) -> list[OpenGame]:
        self.poll()
        now = time.time()
        self.games = {
            game_id: game
            for game_id, game in self.games.items()
            if now - game.seen_at <= GAME_TTL_SECONDS
        }
        return sorted(self.games.values(), key=lambda g: g.seen_at, reverse=True)
