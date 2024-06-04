"""Tests for Broadlink helper functions."""

import pytest
import voluptuous as vol

from homeassistant.components.broadlink.helpers import data_packet, mac_address
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
        with pytest.raises((ValueError, vol.Invalid)):
            mac_address(mac)
