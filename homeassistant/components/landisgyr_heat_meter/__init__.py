"""The Landis+Gyr Heat Meter integration."""
from __future__ import annotations

from ultraheat_api import HeatMeterService, UltraheatReader

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up heat meter from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    reader = UltraheatReader(entry.data[CONF_DEVICE])  # production

    hass.data[DOMAIN][entry.entry_id] = HeatMeterService(reader)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
