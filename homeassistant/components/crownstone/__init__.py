"""Integration for Crownstone."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entry_manager import CrownstoneEntryManager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initiate setup for a Crownstone config entry."""
    manager = CrownstoneEntryManager(hass, entry)

    if not await manager.async_setup():
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = manager

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    manager: CrownstoneEntryManager = hass.data[DOMAIN].pop(entry.entry_id)
    return await manager.async_unload()
