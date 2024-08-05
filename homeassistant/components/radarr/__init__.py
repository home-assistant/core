"""The Radarr component."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import cast

from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_SW_VERSION,
    CONF_API_KEY,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import (
    CalendarUpdateCoordinator,
    DiskSpaceDataUpdateCoordinator,
    HealthDataUpdateCoordinator,
    MoviesDataUpdateCoordinator,
    QueueDataUpdateCoordinator,
    RadarrDataUpdateCoordinator,
    StatusDataUpdateCoordinator,
    T,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]
type RadarrConfigEntry = ConfigEntry[RadarrData]


@dataclass(kw_only=True, slots=True)
class RadarrData:
    """Radarr data type."""

    calendar: CalendarUpdateCoordinator
    disk_space: DiskSpaceDataUpdateCoordinator
    health: HealthDataUpdateCoordinator
    movie: MoviesDataUpdateCoordinator
    queue: QueueDataUpdateCoordinator
    status: StatusDataUpdateCoordinator


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
        calendar=CalendarUpdateCoordinator(hass, host_configuration, radarr),
        disk_space=DiskSpaceDataUpdateCoordinator(hass, host_configuration, radarr),
        health=HealthDataUpdateCoordinator(hass, host_configuration, radarr),
        movie=MoviesDataUpdateCoordinator(hass, host_configuration, radarr),
        queue=QueueDataUpdateCoordinator(hass, host_configuration, radarr),
        status=StatusDataUpdateCoordinator(hass, host_configuration, radarr),
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


class RadarrEntity(CoordinatorEntity[RadarrDataUpdateCoordinator[T]]):
    """Defines a base Radarr entity."""

    _attr_has_entity_name = True
    coordinator: RadarrDataUpdateCoordinator[T]

    def __init__(
        self,
        coordinator: RadarrDataUpdateCoordinator[T],
        description: EntityDescription,
    ) -> None:
        """Create Radarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the Radarr instance."""
        device_info = DeviceInfo(
            configuration_url=self.coordinator.host_configuration.url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=self.coordinator.config_entry.title,
        )
        if isinstance(self.coordinator, StatusDataUpdateCoordinator):
            device_info[ATTR_SW_VERSION] = cast(
                StatusDataUpdateCoordinator, self.coordinator
            ).data.version
        return device_info
