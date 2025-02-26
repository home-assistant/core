"""The LibreHardwareMonitor integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import LibreHardwareMonitorCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up LibreHardwareMonitor from a config entry."""

    lhm_coordinator = LibreHardwareMonitorCoordinator(hass, config_entry)
    await lhm_coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = lhm_coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
