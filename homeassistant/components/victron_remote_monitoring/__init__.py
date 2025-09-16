"""The Victron VRM Solar Forecast integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import (
    VictronRemoteMonitoringConfigEntry,
    VictronRemoteMonitoringDataUpdateCoordinator,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: VictronRemoteMonitoringConfigEntry
) -> bool:
    """Set up VRM from a config entry."""
    coordinator = VictronRemoteMonitoringDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: VictronRemoteMonitoringConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: VictronRemoteMonitoringConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
