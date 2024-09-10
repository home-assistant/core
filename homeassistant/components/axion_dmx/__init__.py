"""The Axion Lighting integration."""

from __future__ import annotations

from libaxion_dmx import AxionDmxApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_PASSWORD, DOMAIN

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Axion Lighting from a config entry."""

    entry.runtime_data = {}

    # Create API instance
    api = AxionDmxApi(entry.data[CONF_HOST], entry.data[CONF_PASSWORD])

    # Validate the API connection (and authentication)
    if not await api.authenticate():
        return False

    # Store the API object in runtime_data
    entry.runtime_data["api"] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
