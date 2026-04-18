"""The AirPatrol integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import AirPatrolConfigEntry, AirPatrolDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: AirPatrolConfigEntry) -> bool:
    """Set up AirPatrol from a config entry."""
    coordinator = AirPatrolDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirPatrolConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
