"""The Radarr component."""
from __future__ import annotations

from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import (
    DiskSpaceDataUpdateCoordinator,
    MoviesDataUpdateCoordinator,
    RadarrDataUpdateCoordinator,
    StatusDataUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
    coordinators: dict[str, RadarrDataUpdateCoordinator] = {
        "status": StatusDataUpdateCoordinator(hass, host_configuration, radarr),
        "disk_space": DiskSpaceDataUpdateCoordinator(hass, host_configuration, radarr),
        "movie": MoviesDataUpdateCoordinator(hass, host_configuration, radarr),
    }
    # Temporary, until we add diagnostic entities
    _version = None
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()
        if isinstance(coordinator, StatusDataUpdateCoordinator):
            _version = coordinator.system_status.version
        coordinator.system_version = _version
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class RadarrEntity(CoordinatorEntity[RadarrDataUpdateCoordinator]):
    """Defines a base Radarr entity."""

    coordinator: RadarrDataUpdateCoordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the Radarr instance."""
        return DeviceInfo(
            configuration_url=self.coordinator.host_configuration.url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=self.coordinator.config_entry.title,
            sw_version=self.coordinator.system_version,
        )
