"""The Steamist integration."""
# pylint: disable=home-assistant-use-runtime-data  # Discovery list is shared across entries

from datetime import timedelta
from typing import Any

from aiosteamist import Steamist

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DISCOVER_SCAN_TIMEOUT, DISCOVERY, DOMAIN
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

type SteamistConfigEntry = ConfigEntry[SteamistDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the steamist component."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[DISCOVERY] = []

    async def _async_discovery(*_: Any) -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT)
        )

    hass.async_create_background_task(
        _async_discovery(), "steamist-discovery", eager_start=True
    )
    async_track_time_interval(hass, _async_discovery, DISCOVERY_INTERVAL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SteamistConfigEntry) -> bool:
    """Set up Steamist from a config entry."""
    host = entry.data[CONF_HOST]
    coordinator = SteamistDataUpdateCoordinator(
        hass,
        entry,
        Steamist(host, async_get_clientsession(hass)),
    )
    await coordinator.async_config_entry_first_refresh()
    if not async_get_discovery(hass, host):
        if discovery := await async_discover_device(hass, host):
            async_update_entry_from_discovery(hass, entry, discovery)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SteamistConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
