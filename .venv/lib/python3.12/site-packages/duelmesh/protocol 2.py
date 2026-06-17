from __future__ import annotations

import json
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from .config import PROTOCOL_VERSION, RESERVED_NICKS, RULESET_ID
from .game import Target, rules_hash

NICK_RE = re.compile(r"^[A-Za-z0-9_-]{3,12}$")
TYPES = {"offer", "join", "accept", "close", "cancel", "forfeit", "roll", "commit", "reveal", "result", "ping"}


class ProtocolError(ValueError):
    pass


def make_msg_id() -> str:
    return secrets.token_hex(4)


def validate_nick(nick: str) -> str:
    if not NICK_RE.fullmatch(nick):
        raise ProtocolError("Nickname must be 3-12 chars: A-Z a-z 0-9 _ -")
    if nick.upper() in RESERVED_NICKS:
        raise ProtocolError("Nickname is reserved")
    return nick


@dataclass(frozen=True)
class Packet:
    t: str
    g: str
    s: str
    n: str
    m: str = field(default_factory=make_msg_id)
    ts: int = 0
    v: int = PROTOCOL_VERSION
    a: str = "dm"
    d: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "a": self.a,
            "v": self.v,
            "t": self.t,
            "g": self.g,
            "n": validate_nick(self.n),
            "s": self.s,
            "m": self.m,
            "ts": self.ts or int(time.time()),
        }
        if self.d:
            data["d"] = self.d
        return data

    def encode(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)


def decode_packet(raw: str | bytes | dict[str, Any]) -> Packet:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw) if isinstance(raw, str) else raw
    if data.get("a") != "dm":
        raise ProtocolError("Not a DuelMesh packet")
    if data.get("v") != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported protocol version")
    if data.get("t") not in TYPES:
        raise ProtocolError("Unsupported packet type")
    for key in ("g", "s", "n"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ProtocolError(f"Missing field {key}")
    validate_nick(data["n"])
    return Packet(
        t=data["t"],
        g=data["g"],
        s=data["s"],
        n=data["n"],
        m=data.get("m") or make_msg_id(),
        ts=int(data.get("ts", 0)),
        d=data.get("d"),
    )


def offer_packet(game_id: str, node_id: str, nick: str) -> Packet:
    return Packet(
        t="offer",
        g=game_id,
        s=node_id,
        n=nick,
        d={"rules": RULESET_ID, "rh": rules_hash()},
    )


def build_packet(packet_type: str, game_id: str, node_id: str, nick: str, **data: Any) -> Packet:
    if packet_type not in TYPES:
        raise ProtocolError(f"Unsupported packet type {packet_type}")
    return Packet(t=packet_type, g=game_id, s=node_id, n=nick, d=data or None)


def commit_payload(round_no: int, commit: str, rules: str = RULESET_ID) -> dict[str, Any]:
    return {"r": round_no, "c": commit, "rules": rules, "rh": rules_hash()}


def reveal_payload(round_no: int, atk: Target, defense: Target, salt: str) -> dict[str, Any]:
    return {"r": round_no, "atk": atk, "def": defense, "salt": salt}
