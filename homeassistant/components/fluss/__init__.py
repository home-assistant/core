"""The Fluss+ integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .api import FlussApiClient
from .const import DOMAIN

LOGGER = logging.getLogger(__package__)

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fluss+ from a config entry."""

    api = FlussApiClient(entry.data[CONF_API_KEY], hass)
    response = await api.async_get_devices()
    LOGGER.warning("D %s", response)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
