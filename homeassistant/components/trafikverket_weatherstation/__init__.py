"""The trafikverket_weatherstation component."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Trafikverket Weatherstation from a config entry."""

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    _LOGGER.debug("Loaded entry for %s", entry.title)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Trafikverket Weatherstation config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _LOGGER.debug("Unloaded entry for %s", entry.title)
        return unload_ok

    return False
