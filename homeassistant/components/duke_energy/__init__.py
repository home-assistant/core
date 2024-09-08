"""The Duke Energy integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import DukeEnergyConfigEntry, DukeEnergyCoordinator

# This integration provides no platforms for now, just inserts statistics
PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: DukeEnergyConfigEntry) -> bool:
    """Set up Duke Energy from a config entry."""

    coordinator = DukeEnergyCoordinator(hass, entry.data)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DukeEnergyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
