"""The Aqvify integration."""
from __future__ import annotations

from aqvify import AqvifyAPI, DeviceDataAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aqvify from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    api = AqvifyAPI(entry.data[CONF_HOST], entry.data[CONF_API_KEY])
    hass.data[DOMAIN][entry.entry_id] = DeviceDataAPI(api)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
