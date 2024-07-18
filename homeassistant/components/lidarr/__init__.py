"""The Lidarr component."""

from __future__ import annotations

from dataclasses import dataclass, fields

from aiopyarr.lidarr_client import LidarrClient
from aiopyarr.models.host_configuration import PyArrHostConfiguration

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import (
    DiskSpaceDataUpdateCoordinator,
    LidarrDataUpdateCoordinator,
    QueueDataUpdateCoordinator,
    StatusDataUpdateCoordinator,
    T,
    WantedDataUpdateCoordinator,
)

type LidarrConfigEntry = ConfigEntry[LidarrData]

PLATFORMS = [Platform.SENSOR]


@dataclass(kw_only=True, slots=True)
class LidarrData:
    """Lidarr data type."""

    disk_space: DiskSpaceDataUpdateCoordinator
    queue: QueueDataUpdateCoordinator
    status: StatusDataUpdateCoordinator
    wanted: WantedDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: LidarrConfigEntry) -> bool:
    """Set up Lidarr from a config entry."""
    host_configuration = PyArrHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        url=entry.data[CONF_URL],
    )
    lidarr = LidarrClient(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass, host_configuration.verify_ssl),
        request_timeout=60,
    )
    data = LidarrData(
        disk_space=DiskSpaceDataUpdateCoordinator(hass, host_configuration, lidarr),
        queue=QueueDataUpdateCoordinator(hass, host_configuration, lidarr),
        status=StatusDataUpdateCoordinator(hass, host_configuration, lidarr),
        wanted=WantedDataUpdateCoordinator(hass, host_configuration, lidarr),
    )
    for field in fields(data):
        coordinator = getattr(data, field.name)
        await coordinator.async_config_entry_first_refresh()
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        configuration_url=entry.data[CONF_URL],
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=DEFAULT_NAME,
        sw_version=data.status.data,
    )
    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LidarrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class LidarrEntity(CoordinatorEntity[LidarrDataUpdateCoordinator[T]]):
    """Defines a base Lidarr entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LidarrDataUpdateCoordinator[T],
        description: EntityDescription,
    ) -> None:
        """Initialize the Lidarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)}
        )
