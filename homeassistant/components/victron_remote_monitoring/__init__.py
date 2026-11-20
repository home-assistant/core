"""The Victron VRM Solar Forecast integration."""

from datetime import datetime

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .coordinator import (
    VictronRemoteMonitoringConfigEntry,
    VictronRemoteMonitoringDataUpdateCoordinator,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: VictronRemoteMonitoringConfigEntry
) -> None:
    """Set up VRM from a config entry."""
    coordinator = VictronRemoteMonitoringDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    async def _async_refresh_at_midnight(_now: datetime) -> None:
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(
            hass, _async_refresh_at_midnight, hour=0, minute=0, second=0
        )
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: VictronRemoteMonitoringConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
