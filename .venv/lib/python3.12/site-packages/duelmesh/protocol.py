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
TYPE_CODES = {
    "offer": "o",
    "join": "j",
    "accept": "a",
    "close": "x",
    "cancel": "k",
    "forfeit": "f",
    "roll": "r",
    "commit": "c",
    "reveal": "v",
    "result": "z",
    "ping": "p",
}
CODE_TYPES = {code: packet_type for packet_type, code in TYPE_CODES.items()}
TARGET_CODES = {"head": "h", "body": "b", "legs": "l"}
CODE_TARGETS = {code: target for target, code in TARGET_CODES.items()}
MINIMAL_TYPES = {"commit", "reveal"}


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
            "t": TYPE_CODES.get(self.t, self.t),
            "g": self.g,
            "s": self.s,
        }
        if self.t not in MINIMAL_TYPES:
            data["n"] = validate_nick(self.n)
            data["m"] = self.m
        if self.t == "offer":
            data["ts"] = self.ts or int(time.time())
        if self.d:
            data["d"] = self.d
        return data

    def encode(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)


def decode_packet(raw: str | bytes | dict[str, Any]) -> Packet:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProtocolError("Not a DuelMesh packet") from exc
    if not isinstance(data, dict):
        raise ProtocolError("Not a DuelMesh packet")
    if data.get("a") != "dm":
        raise ProtocolError("Not a DuelMesh packet")
    if data.get("v") != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported protocol version")
    packet_type = CODE_TYPES.get(data.get("t"), data.get("t"))
    if packet_type not in TYPES:
        raise ProtocolError("Unsupported packet type")
    for key in ("g", "s"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ProtocolError(f"Missing field {key}")
    if data.get("n"):
        validate_nick(data["n"])
    return Packet(
        t=packet_type,
        g=data["g"],
        s=data["s"],
        n=data.get("n", ""),
        m=data.get("m", ""),
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


def commit_payload(round_no: int, commit: str) -> dict[str, Any]:
    return {"r": round_no, "c": commit, "h": rules_hash()}


def reveal_payload(round_no: int, atk: Target, defense: Target, salt: str) -> dict[str, Any]:
    return {"r": round_no, "a": TARGET_CODES[atk], "d": TARGET_CODES[defense], "s": salt}


def reveal_turn(data: dict[str, Any]) -> tuple[Target, Target, str]:
    atk = data.get("atk", data.get("a"))
    defense = data.get("def", data.get("d"))
    salt = data.get("salt", data.get("s"))
    return (
        CODE_TARGETS.get(atk, atk),
        CODE_TARGETS.get(defense, defense),
        salt,
    )
