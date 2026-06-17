from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import MOCK_NODE_PREFIX, Paths, default_paths
from .protocol import ProtocolError, validate_nick


@dataclass
class Profile:
    nickname: str
    node_id: str
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)


def make_mock_node_id() -> str:
    return f"{MOCK_NODE_PREFIX}{secrets.token_hex(4)}"


def load_profile(paths: Paths | None = None) -> Profile | None:
    paths = paths or default_paths()
    data = read_json(paths.profile, None)
    if not data:
        return None
    return Profile(**data)


def save_profile(profile: Profile, paths: Paths | None = None) -> None:
    validate_nick(profile.nickname)
    paths = paths or default_paths()
    write_json(paths.profile, asdict(profile))


def ensure_profile(nickname: str | None = None, node_id: str | None = None, paths: Paths | None = None) -> Profile:
    paths = paths or default_paths()
    profile = load_profile(paths)
    if profile:
        return profile
    if not nickname:
        raise ProtocolError("Nickname is required on first launch")
    profile = Profile(validate_nick(nickname), node_id or make_mock_node_id())
    save_profile(profile, paths)
    return profile


def update_nick(profile: Profile, nickname: str, paths: Paths | None = None) -> Profile:
    profile.nickname = validate_nick(nickname)
    save_profile(profile, paths)
    return profile


def save_state(state: dict[str, Any], paths: Paths | None = None) -> None:
    paths = paths or default_paths()
    write_json(paths.state, state)


def load_state(paths: Paths | None = None) -> dict[str, Any]:
    paths = paths or default_paths()
    return read_json(paths.state, {})

