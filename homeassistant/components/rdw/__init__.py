"""Support for RDW."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RDWConfigEntry, RDWDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: RDWConfigEntry) -> bool:
    """Set up RDW from a config entry."""
    coordinator = RDWDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RDWConfigEntry) -> bool:
    """Unload RDW config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
