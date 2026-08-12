"""Tests for the Papouch UDP discovery logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from aiopapouch.exceptions import DeviceConnectionError

from homeassistant.components.papouch.discovery import (
    PapouchDiscoveryProtocol,
    _get_device_info,
    async_discover_papouch_devices,
)
from homeassistant.core import HomeAssistant


async def test_discovery_protocol() -> None:
    """Test datagram protocol logic."""
    protocol = PapouchDiscoveryProtocol()
    mock_transport = MagicMock(spec=asyncio.DatagramTransport)

    protocol.connection_made(mock_transport)
    mock_transport.sendto.assert_called_once()

    protocol.datagram_received(b"reply", ("192.168.1.100", 30718))
    assert "192.168.1.100" in protocol.discovered_ips


async def test_get_device_info(hass: HomeAssistant) -> None:
    """Test getting device info individually."""
    with (
        patch(
            "homeassistant.components.papouch.discovery.PapouchHTTPClient"
        ) as mock_client_cls,
        patch(
            "homeassistant.components.papouch.discovery.is_device_supported",
            return_value=True,
        ),
    ):
        mock_client = mock_client_cls.return_value

        mock_client.get_device_info = AsyncMock(return_value=("Quido", "Lab"))
        res = await _get_device_info(hass, "1.2.3.4")
        assert res == ("Lab", "Quido")

        mock_client.get_device_info = AsyncMock(return_value=(None, None))
        assert await _get_device_info(hass, "1.2.3.4") is None

        mock_client.get_device_info.side_effect = DeviceConnectionError()
        assert await _get_device_info(hass, "1.2.3.4") is None


async def test_async_discover_devices(hass: HomeAssistant) -> None:
    """Test full device discovery flow."""
    mock_transport = MagicMock()
    mock_protocol = PapouchDiscoveryProtocol()
    mock_protocol.discovered_ips = {"192.168.1.50", "192.168.1.51", "192.168.1.52"}

    async def mock_create_datagram_endpoint(*args, **kwargs):
        return mock_transport, mock_protocol

    with (
        patch("asyncio.get_running_loop") as mock_loop,
        patch(
            "homeassistant.components.papouch.discovery._get_device_info"
        ) as mock_info,
    ):
        mock_loop.return_value.create_datagram_endpoint = mock_create_datagram_endpoint

        async def _mock_get_device_info(hass_obj, ip):
            if ip == "192.168.1.50":
                return ("Lab", "Quido")
            if ip == "192.168.1.51":
                raise TimeoutError
            return None

        mock_info.side_effect = _mock_get_device_info

        results = await async_discover_papouch_devices(hass)

        assert "192.168.1.50" in results
        assert results["192.168.1.50"] == ("Lab", "Quido")
        assert "192.168.1.51" not in results
        assert "192.168.1.52" not in results
