from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from .config import PUBLIC_CHANNEL, default_paths
from .protocol import Packet, ProtocolError, decode_packet


class Transport(ABC):
    node_id: str

    @abstractmethod
    def send_public(self, packet: Packet) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_direct(self, dest_node: str, packet: Packet) -> None:
        raise NotImplementedError

    @abstractmethod
    def receive(self, since: float = 0) -> list[Packet]:
        raise NotImplementedError


class MockTransport(Transport):
    """File-backed local mesh for testing two terminals on one machine."""

    def __init__(self, node_id: str, root: Path | None = None) -> None:
        self.node_id = node_id
        self.root = root or default_paths().mockmesh
        self.root.mkdir(parents=True, exist_ok=True)
        self.bus = self.root / "bus.jsonl"
        self.bus.touch(exist_ok=True)

    def _append(self, scope: str, dest: str, packet: Packet) -> None:
        row = {
            "time": time.time(),
            "scope": scope,
            "dest": dest,
            "packet": packet.to_dict(),
        }
        with self.bus.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    def send_public(self, packet: Packet) -> None:
        self._append("public", "*", packet)

    def send_direct(self, dest_node: str, packet: Packet) -> None:
        self._append("direct", dest_node, packet)

    def receive(self, since: float = 0) -> list[Packet]:
        packets: list[Packet] = []
        with self.bus.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["time"] <= since:
                    continue
                if row["packet"].get("s") == self.node_id:
                    continue
                if row["scope"] == "direct" and row["dest"] != self.node_id:
                    continue
                try:
                    packets.append(decode_packet(row["packet"]))
                except ProtocolError:
                    continue
        return packets


class MeshtasticTransport(Transport):
    def __init__(self, port: str | None = None, ble: str | None = None, channel: str = PUBLIC_CHANNEL) -> None:
        try:
            from pubsub import pub  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional hardware libs
            raise RuntimeError(
                "Meshtastic support needs `pip install -e \".[lora]\"` and connected hardware"
            ) from exc

        self._pub = pub
        if ble:
            try:
                import meshtastic.ble_interface  # type: ignore
            except Exception as exc:  # pragma: no cover - depends on optional hardware libs
                raise RuntimeError("Meshtastic BLE support is unavailable. Install the lora extra and BLE dependencies.") from exc
            self._interface = meshtastic.ble_interface.BLEInterface(ble)
        else:
            try:
                import meshtastic.serial_interface  # type: ignore
            except Exception as exc:  # pragma: no cover - depends on optional hardware libs
                raise RuntimeError("Meshtastic serial support is unavailable. Install the lora extra.") from exc
            self._interface = meshtastic.serial_interface.SerialInterface(devPath=port)
        node_num = int(self._interface.myInfo.my_node_num)  # type: ignore[attr-defined]
        self.node_id = f"!{node_num:08x}"
        self.channel = channel
        self._inbox: list[Packet] = []
        pub.subscribe(self._on_receive, "meshtastic.receive")

    def _on_receive(self, packet: dict, interface: object) -> None:  # pragma: no cover
        decoded = packet.get("decoded", {})
        text = decoded.get("text")
        if not text:
            return
        try:
            incoming = decode_packet(text)
        except ProtocolError:
            return
        if incoming.s != self.node_id:
            self._inbox.append(incoming)

    def send_public(self, packet: Packet) -> None:  # pragma: no cover
        self._interface.sendText(packet.encode(), channelIndex=0)

    def send_direct(self, dest_node: str, packet: Packet) -> None:  # pragma: no cover
        self._interface.sendText(packet.encode(), destinationId=dest_node)

    def receive(self, since: float = 0) -> list[Packet]:  # pragma: no cover
        packets = self._inbox[:]
        self._inbox.clear()
        return packets


def dedupe_packets(packets: Iterable[Packet]) -> list[Packet]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[Packet] = []
    for packet in packets:
        key = (packet.t, packet.g, packet.s, packet.m or packet.encode())
        if key in seen:
            continue
        seen.add(key)
        out.append(packet)
    return out
