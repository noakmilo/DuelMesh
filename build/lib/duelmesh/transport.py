from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import DUELMESH_CHANNEL_INDEX, DUELMESH_CHANNEL_NAME, DUELMESH_CHANNEL_PSK, PUBLIC_CHANNEL, default_paths
from .protocol import Packet, ProtocolError, decode_packet


@dataclass(frozen=True)
class MeshNode:
    node_id: str
    long_name: str
    short_name: str = ""
    last_heard: int | None = None
    hops_away: int | None = None


class Transport(ABC):
    node_id: str
    channel_index: int = 0
    channel_name: str = "mock"

    @abstractmethod
    def send_public(self, packet: Packet) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_direct(self, dest_node: str, packet: Packet) -> None:
        raise NotImplementedError

    @abstractmethod
    def receive(self, since: float = 0) -> list[Packet]:
        raise NotImplementedError

    def list_nodes(self) -> list[MeshNode]:
        return []

    def clear_history(self) -> None:
        return None


class MockTransport(Transport):
    """File-backed local mesh for testing two terminals on one machine."""

    def __init__(self, node_id: str, root: Path | None = None) -> None:
        self.node_id = node_id
        self.channel_index = 0
        self.channel_name = "mock"
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

    def list_nodes(self) -> list[MeshNode]:
        nodes: dict[str, MeshNode] = {}
        with self.bus.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    packet = decode_packet(row["packet"])
                except (json.JSONDecodeError, KeyError, ProtocolError):
                    continue
                if packet.s != self.node_id:
                    nodes[packet.s] = MeshNode(packet.s, packet.n, packet.n[:4], int(row.get("time", 0)))
        return sorted(nodes.values(), key=lambda node: node.last_heard or 0, reverse=True)

    def clear_history(self) -> None:
        self.bus.write_text("", encoding="utf-8")


class MeshtasticTransport(Transport):
    def __init__(
        self,
        port: str | None = None,
        ble: str | None = None,
        channel: str = PUBLIC_CHANNEL,
        channel_index: int = DUELMESH_CHANNEL_INDEX,
    ) -> None:
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
        self.channel_name = channel
        self.channel_index = channel_index
        self._inbox: list[Packet] = []
        self._ensure_duelmesh_channel()
        pub.subscribe(self._on_receive, "meshtastic.receive")

    def _ensure_duelmesh_channel(self) -> None:  # pragma: no cover
        if self.channel_index == 0:
            raise RuntimeError("DuelMesh should use a dedicated Meshtastic channel, not primary channel index 0.")
        local_node = getattr(self._interface, "localNode", None)
        if not local_node or not getattr(local_node, "channels", None):
            return
        try:
            from meshtastic.protobuf import channel_pb2  # type: ignore
        except Exception as exc:
            raise RuntimeError("Meshtastic channel support is unavailable.") from exc

        existing = local_node.getChannelByName(DUELMESH_CHANNEL_NAME)
        if existing:
            self.channel_index = int(existing.index)
            self.channel_name = existing.settings.name or DUELMESH_CHANNEL_NAME
            if existing.settings.psk != DUELMESH_CHANNEL_PSK or existing.role != channel_pb2.Channel.Role.SECONDARY:
                print(f"Updating Meshtastic channel #{existing.index} {DUELMESH_CHANNEL_NAME}.")
                existing.settings.psk = DUELMESH_CHANNEL_PSK
                existing.role = channel_pb2.Channel.Role.SECONDARY
                local_node.writeChannel(existing.index)
            return

        channel = local_node.getChannelByChannelIndex(self.channel_index)
        if channel is None or channel.role != channel_pb2.Channel.Role.DISABLED:
            channel = local_node.getDisabledChannel()
        if not channel:
            raise RuntimeError("No free Meshtastic secondary channel is available for DuelMesh.")

        channel.settings.name = DUELMESH_CHANNEL_NAME
        channel.settings.psk = DUELMESH_CHANNEL_PSK
        channel.role = channel_pb2.Channel.Role.SECONDARY
        print(f"Creating Meshtastic channel #{channel.index} {DUELMESH_CHANNEL_NAME}.")
        local_node.writeChannel(channel.index)
        self.channel_index = int(channel.index)
        self.channel_name = DUELMESH_CHANNEL_NAME

    def _on_receive(self, packet: dict, interface: object) -> None:  # pragma: no cover
        if packet.get("channel", self.channel_index) != self.channel_index:
            return
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
        self._interface.sendText(packet.encode(), channelIndex=self.channel_index)

    def send_direct(self, dest_node: str, packet: Packet) -> None:  # pragma: no cover
        self._interface.sendText(packet.encode(), destinationId=dest_node, wantAck=True, channelIndex=self.channel_index)

    def receive(self, since: float = 0) -> list[Packet]:  # pragma: no cover
        packets = self._inbox[:]
        self._inbox.clear()
        return packets

    def clear_history(self) -> None:  # pragma: no cover
        self._inbox.clear()

    def list_nodes(self) -> list[MeshNode]:  # pragma: no cover
        nodes = getattr(self._interface, "nodes", None) or {}
        out: list[MeshNode] = []
        for node_id, node in nodes.items():
            if node_id == self.node_id:
                continue
            user = node.get("user", {}) if isinstance(node, dict) else {}
            long_name = user.get("longName") or user.get("shortName") or node_id
            out.append(
                MeshNode(
                    node_id=node_id,
                    long_name=long_name,
                    short_name=user.get("shortName", ""),
                    last_heard=node.get("lastHeard") if isinstance(node, dict) else None,
                    hops_away=node.get("hopsAway") if isinstance(node, dict) else None,
                )
            )
        return sorted(out, key=lambda node: node.last_heard or 0, reverse=True)


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
