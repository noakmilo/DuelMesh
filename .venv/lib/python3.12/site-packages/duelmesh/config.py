from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import hashlib


APP_NAME = "DuelMesh"
PROTOCOL_VERSION = 1
RULESET_ID = "duelmesh-v1"
TARGETS = ("head", "body", "legs")
DISPLAY_TARGETS = {"head": "Head", "body": "Body", "legs": "Legs"}
BASE_DAMAGE = {"head": 2.0, "body": 1.0, "legs": 0.5}
BASE_HP = 10.0
RESERVED_NICKS = {"SYSTEM", "ADMIN", "SERVER", "DUELMESH", "MESHGAMES"}
MOCK_NODE_PREFIX = "!mock"
PUBLIC_CHANNEL = "MeshGames"
DUELMESH_CHANNEL_NAME = "DuelMesh"
DUELMESH_CHANNEL_INDEX = 1
DUELMESH_CHANNEL_PSK = hashlib.sha256(b"DuelMesh public Meshtastic channel v1").digest()


@dataclass(frozen=True)
class Paths:
    root: Path
    profile: Path
    state: Path
    mockmesh: Path


def default_paths() -> Paths:
    root = Path(os.environ.get("DUELMESH_HOME", Path.cwd() / ".duelmesh"))
    return Paths(
        root=root,
        profile=root / "profile.json",
        state=root / "state.json",
        mockmesh=root / "mockmesh",
    )
