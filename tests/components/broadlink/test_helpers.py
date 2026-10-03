"""Tests for Broadlink helper functions."""

import probatio
import pytest

from homeassistant.components.broadlink.helpers import (
    data_packet,
    fix_rf_packet_alignment,
    mac_address,
)
from homeassistant.core import HomeAssistant


async def test_padding(hass: HomeAssistant) -> None:
    """Verify that non padding strings are allowed."""
    assert data_packet("Jg") == b"&"
    assert data_packet("Jg=") == b"&"
    assert data_packet("Jg==") == b"&"


async def test_valid_mac_address(hass: HomeAssistant) -> None:
    """Test we convert a valid MAC address to bytes."""
    valid = [
        "A1B2C3D4E5F6",
        "a1b2c3d4e5f6",
        "A1B2-C3D4-E5F6",
        "a1b2-c3d4-e5f6",
        "A1B2.C3D4.E5F6",
        "a1b2.c3d4.e5f6",
        "A1-B2-C3-D4-E5-F6",
        "a1-b2-c3-d4-e5-f6",
        "A1:B2:C3:D4:E5:F6",
        "a1:b2:c3:d4:e5:f6",
    ]
    for mac in valid:
        assert mac_address(mac) == b"\xa1\xb2\xc3\xd4\xe5\xf6"


async def test_invalid_mac_address(hass: HomeAssistant) -> None:
    """Test we do not accept an invalid MAC address."""
    invalid = [
        None,
        123,
        ["a", "b", "c"],
        {"abc": "def"},
        "a1b2c3d4e5f",
        "a1b2.c3d4.e5f",
        "a1-b2-c3-d4-e5-f",
        "a1b2c3d4e5f66",
        "a1b2.c3d4.e5f66",
        "a1-b2-c3-d4-e5-f66",
        "a1b2c3d4e5fg",
        "a1b2.c3d4.e5fg",
        "a1-b2-c3-d4-e5-fg",
        "a1b.2c3d4.e5fg",
        "a1b-2-c3-d4-e5-fg",
    ]
    for mac in invalid:
        with pytest.raises((ValueError, probatio.Invalid)):
            mac_address(mac)


# Two frames of a 433 MHz fixed-code remote as learned by an RM4 Pro: header,
# carrier 433.84 MHz, a stray leading duration (0x35), then short on / 13.5 ms
# sync gap / data bits. The sync gaps land on carrier-on (even) slots.
RF_MISALIGNED = bytes.fromhex("b1c01600b09e0600350d00019a280c0d280d00019a280c0d280d")
RF_ALIGNED = bytes.fromhex("b1c01500b09e06000d00019a280c0d280d00019a280c0d280d")


@pytest.mark.parametrize(
    ("packet", "expected"),
    [
        pytest.param(RF_MISALIGNED, RF_ALIGNED, id="misaligned"),
        pytest.param(RF_ALIGNED, RF_ALIGNED, id="already_aligned"),
        # A single long gap is not enough evidence to realign.
        pytest.param(
            bytes.fromhex("b1c00900b09e0600350d00019a280c"),
            bytes.fromhex("b1c00900b09e0600350d00019a280c"),
            id="single_gap",
        ),
        pytest.param(
            bytes.fromhex("b1c00c00b09e06000d00019a2800019a0c"),
            bytes.fromhex("b1c00c00b09e06000d00019a2800019a0c"),
            id="gaps_on_both_slot_types",
        ),
        pytest.param(
            bytes.fromhex("b1c00600b09e06000001"),
            bytes.fromhex("b1c00600b09e06000001"),
            id="truncated_extended_duration",
        ),
        pytest.param(
            b"\x26" + RF_MISALIGNED[1:], b"\x26" + RF_MISALIGNED[1:], id="ir_packet"
        ),
        pytest.param(
            b"\xb2" + RF_MISALIGNED[1:],
            b"\xb2" + RF_MISALIGNED[1:],
            id="legacy_rf_packet",
        ),
        pytest.param(b"\xb1\xc0", b"\xb1\xc0", id="header_only"),
    ],
)
def test_fix_rf_packet_alignment(packet: bytes, expected: bytes) -> None:
    """Test a learned RM4 Pro RF packet is realigned only when shifted."""
    assert fix_rf_packet_alignment(packet) == expected
