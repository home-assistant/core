"""The Steamist integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiosteamist import Steamist

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

PLATFORMS: list[str] = [Platform.BINARY_SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Steamist from a config entry."""
    client = Steamist(entry.data[CONF_HOST], async_get_clientsession(hass))
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Steamist {entry.data[CONF_HOST]}",
        update_interval=timedelta(seconds=5),
        update_method=client.async_get_status,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
