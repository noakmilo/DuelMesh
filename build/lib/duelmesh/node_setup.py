from __future__ import annotations

import glob
import sys

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


def serial_ports() -> list[str]:
    if sys.platform.startswith("win"):
        return [f"COM{index}" for index in range(1, 33)]
    patterns = ["/dev/cu.*", "/dev/ttyUSB*", "/dev/ttyACM*"]
    ports: list[str] = []
    for pattern in patterns:
        ports.extend(glob.glob(pattern))
    return sorted(dict.fromkeys(ports))


def ble_devices() -> list[tuple[str, str]]:
    try:
        from meshtastic.ble_interface import BLEInterface  # type: ignore
    except Exception as exc:
        raise RuntimeError("BLE support needs meshtastic[cli] installed.") from exc
    devices = BLEInterface.scan()  # pragma: no cover - hardware dependent
    return [(device.name or "Unknown", device.address) for device in devices]


def display_node_setup(profile: Profile, transport_name: str) -> str:
    return f"Transport: {transport_name}\nNickname: {profile.nickname}\nNode ID: {profile.node_id}"
