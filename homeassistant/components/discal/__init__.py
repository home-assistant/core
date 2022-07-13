"""The Discord Calendar integration."""
from __future__ import annotations

import nextcord

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Discord Calendar from a config entry."""
    client = hass.data.setdefault(DOMAIN, {}).setdefault(
        entry.entry_id, nextcord.Client()
    )
    await client.login(entry.data["token"])
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id].close()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
