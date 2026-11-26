"""The Victron VRM Solar Forecast integration."""

from datetime import datetime

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import (
    VictronRemoteMonitoringConfigEntry,
    VictronRemoteMonitoringDataUpdateCoordinator,
)
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Victron Remote Monitoring integration."""
    async_setup_services(hass)
    return True


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
