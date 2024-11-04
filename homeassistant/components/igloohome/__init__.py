"""The igloohome integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import api

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.LOCK]

type MyConfigEntry = ConfigEntry[api.Api]


async def async_setup_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    """Set up igloohome from a config entry."""

    entry.runtime_data = api.Api()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
