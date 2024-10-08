"""The Stookwijzer integration."""

from __future__ import annotations

from stookwijzer import Stookwijzer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Stookwijzer from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = Stookwijzer(
        entry.data[CONF_LOCATION][CONF_LATITUDE],
        entry.data[CONF_LOCATION][CONF_LONGITUDE],
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Stookwijzer config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
