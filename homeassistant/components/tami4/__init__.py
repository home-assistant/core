"""The Tami4Edge integration."""
from __future__ import annotations

from Tami4EdgeAPI import Tami4EdgeAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_REFRESH_TOKEN, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up edge from a config entry."""
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)

    try:
        edge = await hass.async_add_executor_job(Tami4EdgeAPI, refresh_token)
    except Exception as ex:
        raise ConfigEntryNotReady(f"Error connecting to API : {ex}") from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = edge

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
