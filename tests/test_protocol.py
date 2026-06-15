import pytest

from duelmesh.game import RULESET_ID, rules_hash
from duelmesh.protocol import ProtocolError, decode_packet, offer_packet, validate_nick


def test_packet_roundtrip_compact_json() -> None:
    packet = offer_packet("K7Q4", "!a1b2", "Camilo")
    raw = packet.encode()
    decoded = decode_packet(raw)

    assert decoded.t == "offer"
    assert decoded.g == "K7Q4"
    assert decoded.m
    assert decoded.d == {"rules": RULESET_ID, "rh": rules_hash()}


@pytest.mark.parametrize("nick", ["Camilo Noa", "🔥Ham🔥", "VeryLongNickname12345", "ADMIN"])
def test_invalid_nicks_rejected(nick: str) -> None:
    with pytest.raises(ProtocolError):
        validate_nick(nick)


@pytest.mark.parametrize("nick", ["Camilo", "Noa87", "Ham_01", "LoRa-King"])
def test_valid_nicks(nick: str) -> None:
    assert validate_nick(nick) == nick
