"""The time_date component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DISPLAY_OPTIONS, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Time & Date from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if entry.data.get(CONF_DISPLAY_OPTIONS):
        # Clean data after first run.
        hass.config_entries.async_update_entry(entry, data={})
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Time & Date config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
