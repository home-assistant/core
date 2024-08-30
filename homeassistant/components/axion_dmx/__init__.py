"""The Axion Lighting integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .axion_dmx_api import AxionDmxApi  # Import the API class
from .const import CONF_LIGHT_TYPE, DOMAIN

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Axion Lighting from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Create API instance
    api = AxionDmxApi(entry.data["host"], entry.data["password"])

    # Validate the API connection (and authentication)
    if not await api.authenticate():
        return False

    # Store an API object for your platforms to access
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "channel": entry.data["channel"],
        "light_type": entry.data[CONF_LIGHT_TYPE],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
