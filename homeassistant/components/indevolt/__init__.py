"""Home Assistant integration for indevolt device."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import IndevoltConfigEntry, IndevoltCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Set up indevolt integration entry using given configuration."""
    coordinator = IndevoltCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Unload a config entry / clean up resources (when integration is removed / reloaded)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
