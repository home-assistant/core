"""Support for Fumis pellet stoves."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import FumisConfigEntry, FumisDataUpdateCoordinator

PLATFORMS = [Platform.BUTTON, Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: FumisConfigEntry) -> bool:
    """Set up Fumis from a config entry."""
    coordinator = FumisDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FumisConfigEntry) -> bool:
    """Unload Fumis config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
