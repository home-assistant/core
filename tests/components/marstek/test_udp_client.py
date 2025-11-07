"""Tests for the Marstek UDP client."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.marstek.udp_client import MarstekUDPClient
from homeassistant.core import HomeAssistant


@pytest.fixture
def udp_client(hass: HomeAssistant) -> MarstekUDPClient:
    """Create UDP client for testing."""
    return MarstekUDPClient(hass)


async def test_async_setup(udp_client: MarstekUDPClient) -> None:
    """Test UDP client setup."""
    await udp_client.async_setup()

    assert udp_client._socket is not None


async def test_async_cleanup(udp_client: MarstekUDPClient) -> None:
    """Test UDP client cleanup."""
    await udp_client.async_setup()
    await udp_client.async_cleanup()

    assert udp_client._socket is None


async def test_send_udp_message(udp_client: MarstekUDPClient) -> None:
    """Test sending UDP message."""
    await udp_client.async_setup()
    message = '{"id": 1, "method": "test"}'

    # Should not raise exception
    await udp_client._send_udp_message(message, "192.168.1.100", 30000)


async def test_discover_devices_no_devices(udp_client: MarstekUDPClient) -> None:
    """Test device discovery with no devices."""
    await udp_client.async_setup()

    with patch.object(
        udp_client, "send_broadcast_request", return_value=[]
    ) as mock_broadcast:
        devices = await udp_client.discover_devices(use_cache=False)

        assert devices == []
        mock_broadcast.assert_called_once()


async def test_discover_devices_with_devices(
    udp_client: MarstekUDPClient, mock_discovery_response: dict
) -> None:
    """Test device discovery with devices found."""
    await udp_client.async_setup()

    with patch.object(
        udp_client,
        "send_broadcast_request",
        return_value=[mock_discovery_response],
    ) as mock_broadcast:
        devices = await udp_client.discover_devices(use_cache=False)

        assert len(devices) == 1
        assert devices[0]["device_type"] == "ES5"
        assert devices[0]["ip"] == "192.168.1.100"
        mock_broadcast.assert_called_once()


async def test_discover_devices_cache(
    udp_client: MarstekUDPClient, mock_discovery_response: dict
) -> None:
    """Test device discovery with cache."""
    await udp_client.async_setup()

    with patch.object(
        udp_client,
        "send_broadcast_request",
        return_value=[mock_discovery_response],
    ) as mock_broadcast:
        # First call
        devices1 = await udp_client.discover_devices(use_cache=False)
        assert len(devices1) == 1

        # Second call with cache
        devices2 = await udp_client.discover_devices(use_cache=True)
        assert len(devices2) == 1

        # Should only call broadcast once
        assert mock_broadcast.call_count == 1


async def test_clear_discovery_cache(
    udp_client: MarstekUDPClient, mock_discovery_response: dict
) -> None:
    """Test clearing discovery cache."""
    await udp_client.async_setup()

    with patch.object(
        udp_client,
        "send_broadcast_request",
        return_value=[mock_discovery_response],
    ) as mock_broadcast:
        await udp_client.discover_devices(use_cache=False)

        udp_client.clear_discovery_cache()

        await udp_client.discover_devices(use_cache=True)

        # Should call broadcast twice
        assert mock_broadcast.call_count == 2


async def test_polling_control(udp_client: MarstekUDPClient) -> None:
    """Test polling control functionality."""
    await udp_client.async_setup()

    device_ip = "192.168.1.100"

    assert not udp_client.is_polling_paused(device_ip)

    await udp_client.pause_polling(device_ip)
    assert udp_client.is_polling_paused(device_ip)

    await udp_client.resume_polling(device_ip)
    assert not udp_client.is_polling_paused(device_ip)


async def test_get_broadcast_addresses(udp_client: MarstekUDPClient) -> None:
    """Test getting broadcast addresses."""
    await udp_client.async_setup()

    addresses = udp_client._get_broadcast_addresses()

    assert "255.255.255.255" in addresses
    assert isinstance(addresses, list)


async def test_cache_validity(udp_client: MarstekUDPClient) -> None:
    """Test cache validity checking."""
    await udp_client.async_setup()

    assert not udp_client._is_cache_valid()

    udp_client._discovery_cache = [{"device_type": "ES5"}]
    udp_client._cache_timestamp = asyncio.get_event_loop().time()

    assert udp_client._is_cache_valid()

    udp_client._cache_timestamp = asyncio.get_event_loop().time() - 100

    assert not udp_client._is_cache_valid()


async def test_send_request_invalid_message(udp_client: MarstekUDPClient) -> None:
    """Test sending invalid message format."""
    await udp_client.async_setup()

    invalid_message = "not json"

    with pytest.raises(ValueError):
        await udp_client.send_request(
            invalid_message, "192.168.1.100", 30000, timeout=0.1
        )
