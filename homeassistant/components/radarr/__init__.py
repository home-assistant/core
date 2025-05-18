"""The Radarr component."""

from __future__ import annotations

from dataclasses import fields

from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    CalendarUpdateCoordinator,
    DiskSpaceDataUpdateCoordinator,
    HealthDataUpdateCoordinator,
    MoviesDataUpdateCoordinator,
    QueueDataUpdateCoordinator,
    RadarrConfigEntry,
    RadarrData,
    RadarrDataUpdateCoordinator,
    StatusDataUpdateCoordinator,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: RadarrConfigEntry) -> bool:
    """Set up Radarr from a config entry."""
    host_configuration = PyArrHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        url=entry.data[CONF_URL],
    )
    radarr = RadarrClient(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
    )
    data = RadarrData(
        calendar=CalendarUpdateCoordinator(hass, entry, host_configuration, radarr),
        disk_space=DiskSpaceDataUpdateCoordinator(
            hass, entry, host_configuration, radarr
        ),
        health=HealthDataUpdateCoordinator(hass, entry, host_configuration, radarr),
        movie=MoviesDataUpdateCoordinator(hass, entry, host_configuration, radarr),
        queue=QueueDataUpdateCoordinator(hass, entry, host_configuration, radarr),
        status=StatusDataUpdateCoordinator(hass, entry, host_configuration, radarr),
    )
    for field in fields(data):
        coordinator: RadarrDataUpdateCoordinator = getattr(data, field.name)
        # Movie update can take a while depending on Radarr database size
        if field.name == "movie":
            entry.async_create_background_task(
                hass,
                coordinator.async_config_entry_first_refresh(),
                "radarr.movie-coordinator-first-refresh",
            )
            continue
        await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RadarrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
