from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from typing import Any, Literal

from .config import BASE_DAMAGE, BASE_HP, RULESET_ID, TARGETS

Target = Literal["head", "body", "legs"]
Outcome = Literal["active", "p1", "p2", "draw"]


RULES_V1: dict[str, Any] = {
    "ruleset": RULESET_ID,
    "version": 1,
    "base_hp": BASE_HP,
    "damage": BASE_DAMAGE,
    "classes_enabled": False,
    "classes": {
        "v1_default": {"hp": BASE_HP, "head_bonus": 0, "block_bonus": False}
    },
}


def rules_hash(rules: dict[str, Any] | None = None) -> str:
    payload = json.dumps(rules or RULES_V1, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def normalize_target(value: str) -> Target:
    target = value.lower()
    if target not in TARGETS:
        raise ValueError(f"Invalid target: {value}")
    return target  # type: ignore[return-value]


def make_salt() -> str:
    return secrets.token_hex(8)


def turn_commit(round_no: int, atk: Target, defense: Target, salt: str) -> str:
    raw = f"{round_no}|{atk}|{defense}|{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_commit(nick: str, player_class: str, loadout: str, ruleset: str, salt: str) -> str:
    raw = f"{nick}|{player_class}|{loadout}|{ruleset}|{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TurnChoice:
    atk: Target
    defense: Target
    salt: str = field(default_factory=make_salt)

    @property
    def short(self) -> dict[str, str]:
        return {"atk": self.atk, "def": self.defense, "salt": self.salt}


@dataclass
class PlayerState:
    node_id: str
    nick: str
    hp: float = BASE_HP


@dataclass(frozen=True)
class RoundResult:
    round_no: int
    p1_damage: float
    p2_damage: float
    p1_hp: float
    p2_hp: float
    p1_blocked: bool
    p2_blocked: bool
    outcome: Outcome


@dataclass
class DuelState:
    game_id: str
    p1: PlayerState
    p2: PlayerState
    round_no: int = 1
    history: list[dict[str, Any]] = field(default_factory=list)
    outcome: Outcome = "active"

    def apply_round(self, p1_turn: TurnChoice, p2_turn: TurnChoice) -> RoundResult:
        if self.outcome != "active":
            raise ValueError("Duel is already finished")

        p2_blocked = p2_turn.defense == p1_turn.atk
        p1_blocked = p1_turn.defense == p2_turn.atk
        p2_damage = 0.0 if p2_blocked else BASE_DAMAGE[p1_turn.atk]
        p1_damage = 0.0 if p1_blocked else BASE_DAMAGE[p2_turn.atk]

        self.p1.hp = max(0.0, self.p1.hp - p1_damage)
        self.p2.hp = max(0.0, self.p2.hp - p2_damage)

        if self.p1.hp <= 0 and self.p2.hp <= 0:
            self.outcome = "draw"
        elif self.p1.hp <= 0:
            self.outcome = "p2"
        elif self.p2.hp <= 0:
            self.outcome = "p1"

        result = RoundResult(
            round_no=self.round_no,
            p1_damage=p1_damage,
            p2_damage=p2_damage,
            p1_hp=self.p1.hp,
            p2_hp=self.p2.hp,
            p1_blocked=p1_blocked,
            p2_blocked=p2_blocked,
            outcome=self.outcome,
        )
        self.history.append(
            {
                "round": self.round_no,
                "p1": p1_turn.short,
                "p2": p2_turn.short,
                "result": result.__dict__,
            }
        )
        self.round_no += 1
        return result


def replay(duel: DuelState) -> Outcome:
    fresh = DuelState(
        game_id=duel.game_id,
        p1=PlayerState(duel.p1.node_id, duel.p1.nick),
        p2=PlayerState(duel.p2.node_id, duel.p2.nick),
    )
    for item in duel.history:
        p1 = TurnChoice(item["p1"]["atk"], item["p1"]["def"], item["p1"]["salt"])
        p2 = TurnChoice(item["p2"]["atk"], item["p2"]["def"], item["p2"]["salt"])
        fresh.apply_round(p1, p2)
    return fresh.outcome

