from __future__ import annotations

from .storage import Profile


def meshtastic_long_name() -> str | None:
    try:
        import meshtastic.serial_interface  # type: ignore
    except Exception:
        return None
    try:  # pragma: no cover - hardware dependent
        interface = meshtastic.serial_interface.SerialInterface()
        node = interface.getMyNodeInfo()
        user = node.get("user", {})
        return user.get("longName") or user.get("shortName")
    except Exception:
        return None


def display_node_setup(profile: Profile, transport_name: str) -> str:
    return f"Transport: {transport_name}\nNickname: {profile.nickname}\nNode ID: {profile.node_id}"

