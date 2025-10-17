"""DayBetter Services integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .daybetter_api import DayBetterApi

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DayBetter Services from a config entry."""
    _LOGGER.debug("Setting up DayBetter Services integration")

    # Initialize the API client
    token = entry.data.get("token")
    if not token:
        _LOGGER.error("No token found in config entry")
        return False

    api = DayBetterApi(hass, token)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"api": api}

    # Fetch devices and store them
    devices = await api.fetch_devices()
    hass.data[DOMAIN][entry.entry_id]["devices"] = devices

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading DayBetter Services integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
