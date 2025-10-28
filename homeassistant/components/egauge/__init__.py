"""Integration for eGauge energy monitors."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import EgaugeConfigEntry, EgaugeDataCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EgaugeConfigEntry) -> bool:
    """Set up eGauge from a config entry."""

    coordinator = EgaugeDataCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Setup sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EgaugeConfigEntry) -> bool:
    """Unload eGauge config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
