from duelmesh.protocol import build_packet
from duelmesh.transport import MockTransport


def test_mock_transport_public_and_direct(tmp_path) -> None:
    a = MockTransport("!a", tmp_path)
    b = MockTransport("!b", tmp_path)
    c = MockTransport("!c", tmp_path)

    a.send_public(build_packet("ping", "GAME", "!a", "Alice"))
    assert [p.t for p in b.receive()] == ["ping"]

    a.send_direct("!b", build_packet("cancel", "GAME", "!a", "Alice"))
    assert [p.t for p in b.receive()] == ["ping", "cancel"]
    assert [p.t for p in c.receive()] == ["ping"]

