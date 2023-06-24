"""The Steamist integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiosteamist import Steamist

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DISCOVER_SCAN_TIMEOUT, DISCOVERY, DOMAIN, STARTUP_SCAN_TIMEOUT
from .coordinator import SteamistDataUpdateCoordinator
from .discovery import (
    async_discover_device,
    async_discover_devices,
    async_get_discovery,
    async_trigger_discovery,
    async_update_entry_from_discovery,
)

PLATFORMS: list[str] = [Platform.SENSOR, Platform.SWITCH]
DISCOVERY_INTERVAL = timedelta(minutes=15)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the steamist component."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[DISCOVERY] = await async_discover_devices(hass, STARTUP_SCAN_TIMEOUT)

    async def _async_discovery(*_: Any) -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT)
        )

    async_trigger_discovery(hass, domain_data[DISCOVERY])
    async_track_time_interval(hass, _async_discovery, DISCOVERY_INTERVAL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Steamist from a config entry."""
    host = entry.data[CONF_HOST]
    coordinator = SteamistDataUpdateCoordinator(
        hass,
        Steamist(host, async_get_clientsession(hass)),
        host,
        entry.data.get(CONF_NAME),  # Only found from discovery
    )
    await coordinator.async_config_entry_first_refresh()
    if not async_get_discovery(hass, host):
        if discovery := await async_discover_device(hass, host):
            async_update_entry_from_discovery(hass, entry, discovery)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
