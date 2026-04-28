"""Refoss devices platform loader."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .bridge import DiscoveryService, RefossConfigEntry
from .const import DISCOVERY_SCAN_INTERVAL
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_scan_update(_=None):
        await refoss_discovery.discovery.broadcast_msg()

    await _async_scan_update()

    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_scan_update, timedelta(seconds=DISCOVERY_SCAN_INTERVAL)
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RefossConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.discovery.clean_up()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
