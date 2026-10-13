"""Refoss devices platform loader."""

import asyncio
from datetime import timedelta
from typing import Final

from refoss_ha.discovery import Discovery

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .bridge import DiscoveryService, RefossConfigEntry
from .const import DISCOVERY_SCAN_INTERVAL, DISCOVERY_SERVER
from .util import refoss_discovery_server

PLATFORMS: Final = [
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: RefossConfigEntry) -> bool:
    """Set up Refoss from a config entry."""
    discover = await refoss_discovery_server(hass)
    refoss_discovery = DiscoveryService(hass, entry, discover)
    entry.runtime_data = refoss_discovery
    if discover.tasks:
        await asyncio.gather(*discover.tasks, return_exceptions=True)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_scan_update(_=None) -> None:
        await refoss_discovery.async_scan()

    await _async_scan_update()

    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_scan_update, timedelta(seconds=DISCOVERY_SCAN_INTERVAL)
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RefossConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        discovery = entry.runtime_data.discovery
        discovery.remove_listener(entry.runtime_data)
        _close_discovery(discovery)
        hass.data.pop(DISCOVERY_SERVER, None)
    return unload_ok


def _close_discovery(discovery: Discovery) -> None:
    """Release the UDP endpoint so a later setup can bind again."""
    if (transport := getattr(discovery, "transport", None)) is not None:
        transport.close()
    if (sock := getattr(discovery, "sock", None)) is not None:
        sock.close()
