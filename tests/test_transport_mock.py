from duelmesh.protocol import build_packet
from duelmesh.config import DUELMESH_CHANNEL_NAME, DUELMESH_CHANNEL_PSK
from duelmesh.transport import MeshtasticTransport, MockTransport


class FakeSettings:
    def __init__(self, name: str = "", psk: bytes = b"") -> None:
        self.name = name
        self.psk = psk


class FakeChannel:
    def __init__(self, index: int, role: int, name: str = "", psk: bytes = b"") -> None:
        self.index = index
        self.role = role
        self.settings = FakeSettings(name, psk)


class FakeLocalNode:
    def __init__(self, channels: list[FakeChannel]) -> None:
        self.channels = channels
        self.written: list[int] = []

    def getChannelByName(self, name: str):
        for channel in self.channels:
            if channel.settings.name == name:
                return channel
        return None

    def getChannelByChannelIndex(self, channel_index: int):
        return self.channels[channel_index] if 0 <= channel_index < len(self.channels) else None

    def getDisabledChannel(self):
        for channel in self.channels:
            if channel.role == 0:
                return channel
        return None

    def writeChannel(self, channel_index: int) -> None:
        self.written.append(channel_index)


class FakeInterface:
    def __init__(self, local_node: FakeLocalNode) -> None:
        self.localNode = local_node


def test_mock_transport_public_and_direct(tmp_path) -> None:
    a = MockTransport("!a", tmp_path)
    b = MockTransport("!b", tmp_path)
    c = MockTransport("!c", tmp_path)

    a.send_public(build_packet("ping", "GAME", "!a", "Alice"))
    assert [p.t for p in b.receive()] == ["ping"]

    a.send_direct("!b", build_packet("cancel", "GAME", "!a", "Alice"))
    assert [p.t for p in b.receive()] == ["ping", "cancel"]
    assert [p.t for p in c.receive()] == ["ping"]


def test_meshtastic_transport_reuses_matching_duelmesh_channel() -> None:
    local_node = FakeLocalNode(
        [
            FakeChannel(0, 1, "Primary"),
            FakeChannel(1, 2, DUELMESH_CHANNEL_NAME, DUELMESH_CHANNEL_PSK),
            FakeChannel(2, 0),
        ]
    )
    transport = MeshtasticTransport.__new__(MeshtasticTransport)
    transport.channel_index = 1
    transport._interface = FakeInterface(local_node)

    transport._ensure_duelmesh_channel()

    assert transport.channel_index == 1
    assert local_node.written == []


def test_meshtastic_transport_normalizes_existing_duelmesh_channel_psk() -> None:
    local_node = FakeLocalNode(
        [
            FakeChannel(0, 1, "Primary"),
            FakeChannel(1, 2, DUELMESH_CHANNEL_NAME, b"custom"),
            FakeChannel(2, 0),
        ]
    )
    transport = MeshtasticTransport.__new__(MeshtasticTransport)
    transport.channel_index = 1
    transport._interface = FakeInterface(local_node)

    transport._ensure_duelmesh_channel()

    assert transport.channel_index == 1
    assert local_node.channels[1].settings.psk == DUELMESH_CHANNEL_PSK
    assert local_node.written == [1]


def test_meshtastic_transport_creates_duelmesh_channel_once() -> None:
    local_node = FakeLocalNode(
        [
            FakeChannel(0, 1, "Primary"),
            FakeChannel(1, 0),
            FakeChannel(2, 0),
        ]
    )
    transport = MeshtasticTransport.__new__(MeshtasticTransport)
    transport.channel_index = 1
    transport._interface = FakeInterface(local_node)

    transport._ensure_duelmesh_channel()

    created = local_node.channels[1]
    assert transport.channel_index == 1
    assert created.settings.name == DUELMESH_CHANNEL_NAME
    assert created.settings.psk == DUELMESH_CHANNEL_PSK
    assert created.role == 2
    assert local_node.written == [1]
