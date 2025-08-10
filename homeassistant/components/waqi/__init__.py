"""The World Air Quality Index (WAQI) integration."""

from __future__ import annotations

from aiowaqi import WAQIClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import WAQIConfigEntry, WAQIDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WAQIConfigEntry) -> bool:
    """Set up World Air Quality Index (WAQI) from a config entry."""

    client = WAQIClient(session=async_get_clientsession(hass))
    client.authenticate(entry.data[CONF_API_KEY])

    waqi_coordinator = WAQIDataUpdateCoordinator(hass, entry, client)
    await waqi_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = waqi_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WAQIConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
