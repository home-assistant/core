"""The Sutro integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SutroDataUpdateCoordinator
from .sutro_api import SutroApi

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sutro from a config entry."""
    api_token = entry.data[CONF_API_TOKEN]
    sutro_api = SutroApi(hass, api_token)
    hass.data[DOMAIN] = sutro_api

    coordinator = SutroDataUpdateCoordinator(hass, sutro_api)
    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN]

    return unload_ok
