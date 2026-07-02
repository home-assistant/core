"""Test AirTouch 3 discovery helpers."""

import asyncio
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

from pyairtouch3 import AirTouch3Discovery

from homeassistant import config_entries
from homeassistant.components.airtouch3 import discovery as airtouch3_discovery
from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.components.airtouch3.discovery import (
    _async_get_discovery_targets,
    async_discover_devices,
    async_trigger_discovery,
)
from homeassistant.core import HomeAssistant


async def test_async_get_discovery_targets_includes_adapter_broadcasts(
    hass: HomeAssistant,
) -> None:
    """Test discovery targets include broadcast addresses from enabled adapters."""
    with (
        patch(
            "homeassistant.components.airtouch3.discovery.network.async_get_ipv4_broadcast_addresses",
            return_value={IPv4Address("255.255.255.255")},
        ),
        patch(
            "homeassistant.components.airtouch3.discovery.network.async_get_adapters",
            return_value=[
                {
                    "auto": True,
                    "default": True,
                    "enabled": True,
                    "index": 1,
                    "ipv4": [{"address": "10.200.6.240", "network_prefix": 24}],
                    "ipv6": [],
                    "name": "eth0",
                },
                {
                    "auto": False,
                    "default": False,
                    "enabled": False,
                    "index": 2,
                    "ipv4": [{"address": "10.200.5.100", "network_prefix": 24}],
                    "ipv6": [],
                    "name": "eth1",
                },
            ],
        ),
    ):
        assert await _async_get_discovery_targets(hass) == [
            "10.200.6.255",
            "255.255.255.255",
        ]


async def test_async_discover_devices_wrapper_waits_for_lock(
    hass: HomeAssistant,
) -> None:
    """Test discovery waits for an in-progress scan."""
    await airtouch3_discovery._DISCOVERY_LOCK.acquire()
    try:
        with patch(
            "homeassistant.components.airtouch3.discovery._async_discover_devices",
            AsyncMock(return_value=[]),
        ) as discover:
            task = asyncio.create_task(async_discover_devices(hass, 1))
            await asyncio.sleep(0)
            assert not task.done()
            airtouch3_discovery._DISCOVERY_LOCK.release()
            assert await task == []
    finally:
        if airtouch3_discovery._DISCOVERY_LOCK.locked():
            airtouch3_discovery._DISCOVERY_LOCK.release()

    discover.assert_awaited_once_with(hass, 1)


async def test_async_discover_devices_no_targets(hass: HomeAssistant) -> None:
    """Test discovery returns no devices when no targets are available."""
    with patch(
        "homeassistant.components.airtouch3.discovery._async_get_discovery_targets",
        AsyncMock(return_value=[]),
    ):
        assert await airtouch3_discovery._async_discover_devices(hass, 1) == []


async def test_async_discover_devices_delegates_to_pyairtouch3(
    hass: HomeAssistant,
) -> None:
    """Test discovery delegates socket probing to pyairtouch3."""
    discoveries = [
        AirTouch3Discovery(host="10.200.5.20", mac="F0FE6B772324", model="AirTouch3")
    ]

    with (
        patch(
            "homeassistant.components.airtouch3.discovery._async_get_discovery_targets",
            AsyncMock(return_value=["10.200.5.255"]),
        ),
        patch(
            "homeassistant.components.airtouch3.discovery.async_discover_targets",
            AsyncMock(return_value=discoveries),
        ) as discover_targets,
    ):
        assert await airtouch3_discovery._async_discover_devices(hass, 1) == discoveries

    discover_targets.assert_awaited_once()


def test_async_trigger_discovery(hass: HomeAssistant) -> None:
    """Test triggering config flows from discovered controllers."""
    discovery = AirTouch3Discovery(
        host="10.200.5.20", mac="F0FE6B772324", model="AirTouch3"
    )

    with patch(
        "homeassistant.components.airtouch3.discovery.discovery_flow.async_create_flow"
    ) as create_flow:
        async_trigger_discovery(hass, [discovery])

    create_flow.assert_called_once_with(
        hass,
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            "host": "10.200.5.20",
            "mac": "F0FE6B772324",
            "model": "AirTouch3",
        },
    )
