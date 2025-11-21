"""The Essent integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import EssentConfigEntry, EssentDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EssentConfigEntry) -> bool:
    """Set up Essent from a config entry."""
    coordinator = EssentDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Start independent schedules for API fetch and listener updates
    # These will continue running regardless of API success/failure
    coordinator.start_schedules()

    entry.async_on_unload(coordinator.async_shutdown)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EssentConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
