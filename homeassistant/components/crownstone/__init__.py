"""Integration for Crownstone."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .entry_manager import CrownstoneConfigEntry, CrownstoneEntryManager


async def async_setup_entry(hass: HomeAssistant, entry: CrownstoneConfigEntry) -> bool:
    """Initiate setup for a Crownstone config entry."""
    manager = CrownstoneEntryManager(hass, entry)

    return await manager.async_setup()


async def async_unload_entry(hass: HomeAssistant, entry: CrownstoneConfigEntry) -> bool:
    """Unload a config entry."""
    return await entry.runtime_data.async_unload()
