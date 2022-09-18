"""The Lidarr component."""
from __future__ import annotations

from aiopyarr.lidarr_client import LidarrClient
from aiopyarr.models.host_configuration import PyArrHostConfiguration

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import (
    DiskSpaceDataUpdateCoordinator,
    LidarrDataUpdateCoordinator,
    QueueDataUpdateCoordinator,
    StatusDataUpdateCoordinator,
    WantedDataUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
    coordinators: dict[str, LidarrDataUpdateCoordinator] = {
        "disk_space": DiskSpaceDataUpdateCoordinator(hass, host_configuration, lidarr),
        "queue": QueueDataUpdateCoordinator(hass, host_configuration, lidarr),
        "status": StatusDataUpdateCoordinator(hass, host_configuration, lidarr),
        "wanted": WantedDataUpdateCoordinator(hass, host_configuration, lidarr),
    }
    # Temporary, until we add diagnostic entities
    _version = None
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()
        if isinstance(coordinator, StatusDataUpdateCoordinator):
            _version = coordinator.data
        coordinator.system_version = _version
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class LidarrEntity(CoordinatorEntity[LidarrDataUpdateCoordinator]):
    """Defines a base Lidarr entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: LidarrDataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the Lidarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.host_configuration.base_url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
            sw_version=coordinator.system_version,
        )
