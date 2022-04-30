"""Integration for Crownstone."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entry_manager import CrownstoneEntryManager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initiate setup for a Crownstone config entry."""
    manager = CrownstoneEntryManager(hass, entry)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    return await manager.async_setup()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.data[DOMAIN][entry.entry_id].async_unload()
    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)
    return unload_ok
