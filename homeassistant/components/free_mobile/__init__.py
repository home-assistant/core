"""The free_mobile component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.NOTIFY]


type FreeMobileConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: FreeMobileConfigEntry) -> bool:
    """Set up Free Mobile from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreeMobileConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
