"""Yeelock integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .device import Yeelock

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yeelock from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    yeelock_device = Yeelock(entry.data, hass)
    hass.data[DOMAIN][entry.unique_id] = yeelock_device
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.data[DOMAIN][entry.unique_id].disconnect()
        hass.data[DOMAIN].pop(entry.unique_id)
    _LOGGER.info("Unload %s", entry.unique_id)
    return unload_ok
