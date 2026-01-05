"""The Devialet integration."""

from __future__ import annotations

from devialet import DevialetApi

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import DevialetConfigEntry, DevialetCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: DevialetConfigEntry) -> bool:
    """Set up Devialet from a config entry."""
    session = async_get_clientsession(hass)
    client = DevialetApi(entry.data[CONF_HOST], session)
    coordinator = DevialetCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DevialetConfigEntry) -> bool:
    """Unload Devialet config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
