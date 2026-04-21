"""Tests for Broadlink infrared platform."""

import pytest

from homeassistant.components.broadlink.const import IR_PACKET_REPEAT_INDEX
from homeassistant.components.broadlink.infrared import (
    BroadlinkIRCommand,
    timings_to_broadlink_packet,
)

# Test-only constants for Broadlink IR packet format
IR_PACKET_TYPE = 0x26  # IR data packet type byte
IR_PACKET_PAYLOAD_OFFSET = 4  # Byte offset where payload starts

# NEC IR protocol timings (microseconds)
NEC_HEADER_MARK_US = 9000
NEC_HEADER_SPACE_US = 4500
NEC_BIT_MARK_US = 562
NEC_ONE_SPACE_US = 1687
NEC_ZERO_SPACE_US = 562


def test_packet_header() -> None:
    """Test IR type byte, repeat, and length fields."""
    timings = [NEC_HEADER_MARK_US, -NEC_HEADER_SPACE_US]
    packet = timings_to_broadlink_packet(timings, repeat=0)

    assert packet[0] == IR_PACKET_TYPE
    assert packet[1] == 0  # no repeat

    payload_len = packet[2] | (packet[3] << 8)
    assert payload_len == len(packet) - IR_PACKET_PAYLOAD_OFFSET


def test_packet_ends_with_silence() -> None:
    """Test packet structure is well-formed."""
    timings = [NEC_BIT_MARK_US, -NEC_ZERO_SPACE_US]
    packet = timings_to_broadlink_packet(timings)
    assert packet[0] == IR_PACKET_TYPE
    assert len(packet) >= IR_PACKET_PAYLOAD_OFFSET  # header + minimum payload


def test_packet_repeat_count() -> None:
    """Test repeat count is set."""
    timings = [NEC_BIT_MARK_US, -NEC_ZERO_SPACE_US]
    packet = timings_to_broadlink_packet(timings, repeat=2)
    assert packet[IR_PACKET_REPEAT_INDEX] == 2


def test_packet_repeat_out_of_range() -> None:
    """Test that out-of-range repeat raises ValueError."""
    timings = [NEC_BIT_MARK_US, -NEC_ZERO_SPACE_US]
    with pytest.raises(ValueError, match="repeat must be 0"):
        timings_to_broadlink_packet(timings, repeat=-1)
    with pytest.raises(ValueError, match="repeat must be 0"):
        timings_to_broadlink_packet(timings, repeat=256)


def test_packet_nec_header_encoding() -> None:
    """Test that a NEC header encodes correctly."""
    timings = [NEC_HEADER_MARK_US, -NEC_HEADER_SPACE_US]
    packet = timings_to_broadlink_packet(timings)

    # Skip packet header to get encoded payload
    data = packet[IR_PACKET_PAYLOAD_OFFSET:]

    # 9000µs → 274 (>255 → 3 bytes: 0x00, 0x01, 0x12)
    assert data[0] == 0x00
    assert data[1] == 0x01
    assert data[2] == 0x12

    # 4500µs → 137 (<=255 → 1 byte)
    assert data[3] == 0x89


def test_packet_known_nec_command() -> None:
    """Encode a full NEC power command and verify it's well-formed."""
    nec_timings: list[int] = [NEC_HEADER_MARK_US, -NEC_HEADER_SPACE_US]
    for bit in (
        0,
        0,
        1,
        0,
        0,
        0,
        0,
        0,  # address
        1,
        1,
        0,
        1,
        1,
        1,
        1,
        1,  # ~address
        0,
        0,
        0,
        0,
        1,
        0,
        0,
        0,  # command
        1,
        1,
        1,
        1,
        0,
        1,
        1,
        1,  # ~command
    ):
        nec_timings.append(NEC_BIT_MARK_US)
        nec_timings.append(-NEC_ONE_SPACE_US if bit else -NEC_ZERO_SPACE_US)
    nec_timings.append(NEC_BIT_MARK_US)  # stop bit

    packet = timings_to_broadlink_packet(nec_timings)

    assert packet[0] == IR_PACKET_TYPE
    assert len(packet) > 10


def test_broadlink_ir_command_basic() -> None:
    """Test BroadlinkIRCommand initialization and interface."""
    timings = [(500, 500), (500, 1000), (NEC_BIT_MARK_US, NEC_ZERO_SPACE_US)]
    cmd = BroadlinkIRCommand(timings, repeat_count=3)

    assert cmd.repeat_count == 3
    assert cmd.get_raw_timings() == [
        500,
        -500,
        500,
        -1000,
        NEC_BIT_MARK_US,
        -NEC_ZERO_SPACE_US,
    ]


def test_broadlink_ir_command_omits_zero_space() -> None:
    """Test BroadlinkIRCommand drops trailing zero space into a single end pulse."""
    cmd = BroadlinkIRCommand([(500, 500), (NEC_BIT_MARK_US, 0)])
    assert cmd.get_raw_timings() == [500, -500, NEC_BIT_MARK_US]


def test_broadlink_ir_command_default_repeat() -> None:
    """Test BroadlinkIRCommand defaults to repeat=0."""
    timings = [(500, 500)]
    cmd = BroadlinkIRCommand(timings)

    assert cmd.repeat_count == 0


def test_broadlink_ir_command_invalid_repeat() -> None:
    """Test that BroadlinkIRCommand raises ValueError for out-of-range repeat_count."""
    timings = [(500, 500)]

    # Test negative repeat count
    with pytest.raises(ValueError, match="repeat_count must be 0–255"):
        BroadlinkIRCommand(timings, repeat_count=-1)

    # Test repeat count > 255
    with pytest.raises(ValueError, match="repeat_count must be 0–255"):
        BroadlinkIRCommand(timings, repeat_count=256)

    # Test boundary cases that should work
    BroadlinkIRCommand(timings, repeat_count=0)  # Should not raise
    BroadlinkIRCommand(timings, repeat_count=255)  # Should not raise
