"""The buienradar integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = [Platform.CAMERA, Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up buienradar from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        for platform in PLATFORMS:
            if (data := entry_data.get(platform)) and (
                unsub := data.unsub_schedule_update
            ):
                unsub()

    return unload_ok


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)
