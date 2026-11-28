"""Tests for Broadlink helper functions."""

from unittest.mock import MagicMock, patch

import probatio
import pytest

from homeassistant.components.broadlink import helpers
from homeassistant.components.broadlink.helpers import (
    async_find_device_by_mac,
    data_packet,
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


@pytest.mark.no_mock_rediscovery
async def test_find_device_by_mac_non_rfc1918() -> None:
    """Test rediscovery rejects non-RFC1918 addresses."""
    assert await async_find_device_by_mac("AABBCCDDEEFF", "8.8.8.8") is None
    assert await async_find_device_by_mac("AABBCCDDEEFF", "127.0.0.1") is None
    assert await async_find_device_by_mac("AABBCCDDEEFF", "invalid_ip") is None


@pytest.mark.no_mock_rediscovery
async def test_find_device_by_mac_discovery_and_cache() -> None:
    """Test device rediscovery and cache behavior."""
    helpers._DISCOVERED_CACHE.clear()
    helpers._SUBNET_LAST_SCANNED.clear()

    mock_dev = MagicMock()
    mock_dev.mac = bytes.fromhex("aabbccddeeff")

    async def mock_hello(ip: str) -> MagicMock:
        if ip == "192.168.1.50":
            return mock_dev
        raise TimeoutError

    with patch(
        "homeassistant.components.broadlink.helpers.blk.hello", side_effect=mock_hello
    ) as mock_blk:
        result = await async_find_device_by_mac("AA:BB:CC:DD:EE:FF", "192.168.1.1")
        assert result is not None
        assert result[0] == "192.168.1.50"
        assert result[1] is mock_dev
        first_call_count = mock_blk.call_count

        # Second lookup should hit positive cache without invoking hello again
        cached_result = await async_find_device_by_mac("aabbccddeeff", "192.168.1.1")
        assert cached_result is not None
        assert cached_result[0] == "192.168.1.50"
        assert mock_blk.call_count == first_call_count

    helpers._DISCOVERED_CACHE.clear()
    helpers._SUBNET_LAST_SCANNED.clear()
