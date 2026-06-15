"""Tests for PowerShades packet building and parsing."""

import struct

from homeassistant.components.powershades.const import OP_GET_STATUS
from homeassistant.components.powershades.protocol import (
    HEADER_SIZE,
    StatusReply,
    battery_percentage,
    build_packet,
    build_set_limit_payload,
    build_set_name_payload,
    build_set_position_payload,
    crc16_xmodem,
    parse_device_name_reply,
    parse_header,
    parse_serial_reply,
    parse_shade_name_reply,
    parse_status_reply,
    verify_packet,
)


def test_build_packet_roundtrip() -> None:
    """A packet built by build_packet passes verify_packet and parses back."""
    packet = build_packet(OP_GET_STATUS, sequence=5, channel=1, payload=b"\x01\x02")
    assert verify_packet(packet)

    header = parse_header(packet)
    assert header is not None
    assert header.op == OP_GET_STATUS
    assert header.sequence == 5
    assert header.channel == 1
    assert header.length == 2


def test_verify_packet_rejects_corrupted_crc() -> None:
    """A packet with a tampered CRC fails verification."""
    packet = build_packet(OP_GET_STATUS)
    corrupted = bytearray(packet)
    corrupted[2] ^= 0xFF  # flip a bit in the CRC field
    assert not verify_packet(bytes(corrupted))


def test_verify_packet_rejects_short_packet() -> None:
    """A packet shorter than its declared length fails verification."""
    packet = build_packet(OP_GET_STATUS, payload=b"\x01\x02\x03\x04")
    assert not verify_packet(packet[:-1])


def test_parse_header_too_short() -> None:
    """A packet shorter than the header returns None."""
    assert parse_header(b"\x00\x01") is None


def test_crc16_xmodem_known_value() -> None:
    """The CRC matches a known CRC16-XMODEM test vector."""
    assert crc16_xmodem(b"123456789") == 0x31C3


def test_parse_serial_reply() -> None:
    """A Get Serial Number reply is parsed into model/direction/serial/dhcp."""
    # model, pad, pad, direction, serial low, serial high, dhcp_enabled
    payload = struct.pack("<BBBBIIB", 1, 0, 0, 2, 100, 0, 1)
    payload += b"\x00" * (24 - HEADER_SIZE - len(payload))
    packet = build_packet(0x00, payload=payload)

    parsed = parse_serial_reply(packet)
    assert parsed == {
        "model": 1,
        "direction": 2,
        "serial": 100,
        "dhcp_enabled": True,
    }


def test_parse_serial_reply_too_short() -> None:
    """A truncated serial reply returns None."""
    assert parse_serial_reply(b"\x00" * 10) is None


def test_parse_status_reply_in_range_position() -> None:
    """A valid status reply with a 0-100 percent is parsed."""
    payload = struct.pack("<hhHHIIIhII", 42, 0, 0, 3700, 0, 0, 0, 20, 42, 0)
    packet = build_packet(OP_GET_STATUS, payload=payload)

    status = parse_status_reply(packet)
    assert status == StatusReply(position=42, battery_mv=3700)


def test_parse_status_reply_out_of_range_position_is_unknown() -> None:
    """An out-of-range percent (e.g. while limits are unset) is reported as unknown."""
    payload = struct.pack("<hhHHIIIhII", 200, 0, 0, 3700, 0, 0, 0, 20, 200, 0)
    packet = build_packet(OP_GET_STATUS, payload=payload)

    status = parse_status_reply(packet)
    assert status == StatusReply(position=None, battery_mv=3700)


def test_parse_status_reply_wrong_op_returns_none() -> None:
    """A reply for a different op is not parsed as a status reply."""
    payload = struct.pack("<hhHHIIIhII", 42, 0, 0, 3700, 0, 0, 0, 20, 42, 0)
    packet = build_packet(0x00, payload=payload)
    assert parse_status_reply(packet) is None


def test_parse_shade_name_reply() -> None:
    """A Get PoE Shade Name reply is decoded into the shade's name."""
    payload = b"\x00" + b"Bedroom Shade".ljust(50, b"\x00")
    packet = build_packet(0x34, payload=payload)
    assert parse_shade_name_reply(packet) == "Bedroom Shade"


def test_parse_shade_name_reply_too_short() -> None:
    """A truncated shade name reply returns None."""
    assert parse_shade_name_reply(b"\x00" * 10) is None


def test_parse_device_name_reply() -> None:
    """A Get Device Name reply is decoded into the device's name."""
    payload = b"RF Gateway".ljust(50, b"\x00")
    packet = build_packet(0x3A, payload=payload)
    assert parse_device_name_reply(packet) == "RF Gateway"


def test_parse_device_name_reply_empty_is_none() -> None:
    """An all-blank name decodes to None."""
    payload = b"\x00" * 50
    packet = build_packet(0x3A, payload=payload)
    assert parse_device_name_reply(packet) is None


def test_parse_device_name_reply_too_short() -> None:
    """A truncated device name reply returns None."""
    assert parse_device_name_reply(b"\x00" * 10) is None


def test_parse_status_reply_short_payload_returns_none() -> None:
    """A status reply with a too-short payload returns None."""
    packet = build_packet(OP_GET_STATUS, payload=b"\x00" * 10)
    assert parse_status_reply(packet) is None


def test_build_set_position_payload() -> None:
    """The set-position payload encodes the requested percent."""
    payload = build_set_position_payload(75)
    mask, percent, tilt, channel_mask = struct.unpack("<HhhI", payload)
    assert mask == 0x0001
    assert percent == 75
    assert tilt == 0
    assert channel_mask == 0


def test_build_set_limit_payload() -> None:
    """The set-limit payload encodes the limit type."""
    assert build_set_limit_payload(0x0001) == struct.pack("<H", 0x0001)


def test_build_set_name_payload() -> None:
    """The set-name payload sets the "set" flag and pads/truncates the name."""
    payload = build_set_name_payload("Office")
    assert payload[0:1] == b"\x01"
    assert payload[1:].rstrip(b"\x00") == b"Office"
    assert len(payload) == 51

    long_payload = build_set_name_payload("x" * 100)
    assert len(long_payload) == 51
    assert long_payload[1:] == b"x" * 50


def test_battery_percentage_bounds() -> None:
    """Battery voltage is mapped to a 0-100% range, clamped at the ends."""
    assert battery_percentage(None) is None
    assert battery_percentage(2800) == 0
    assert battery_percentage(4200) == 100
    assert battery_percentage(4500) == 100
    assert battery_percentage(3600) == 50
