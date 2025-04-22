"""The tests for the dhcp WebSocket API."""

import asyncio
from collections.abc import Callable
from unittest.mock import patch

import aiodhcpwatcher

from homeassistant.components.dhcp import DOMAIN
from homeassistant.core import EVENT_HOMEASSISTANT_STARTED, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


async def test_subscribe_discovery(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test dhcp subscribe_discovery."""
    saved_callback: Callable[[aiodhcpwatcher.DHCPRequest], None] | None = None

    async def mock_start(
        callback: Callable[[aiodhcpwatcher.DHCPRequest], None],
    ) -> None:
        """Mock start."""
        nonlocal saved_callback
        saved_callback = callback

    with (
        patch("homeassistant.components.dhcp.aiodhcpwatcher.async_start", mock_start),
        patch("homeassistant.components.dhcp.DiscoverHosts"),
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    saved_callback(aiodhcpwatcher.DHCPRequest("4.3.2.2", "happy", "44:44:33:11:23:12"))
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "dhcp/subscribe_discovery",
        }
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["success"]

    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {
        "add": [
            {
                "hostname": "happy",
                "ip_address": "4.3.2.2",
                "mac_address": "44:44:33:11:23:12",
            }
        ]
    }

    saved_callback(aiodhcpwatcher.DHCPRequest("4.3.2.1", "sad", "44:44:33:11:23:13"))

    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {
        "add": [
            {
                "hostname": "sad",
                "ip_address": "4.3.2.1",
                "mac_address": "44:44:33:11:23:13",
            }
        ]
    }
