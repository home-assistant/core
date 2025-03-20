"""The Lidarr component."""

from __future__ import annotations

from dataclasses import fields

from aiopyarr.lidarr_client import LidarrClient
from aiopyarr.models.host_configuration import PyArrHostConfiguration

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import (
    AlbumsDataUpdateCoordinator,
    DiskSpaceDataUpdateCoordinator,
    LidarrConfigEntry,
    LidarrData,
    QueueDataUpdateCoordinator,
    StatusDataUpdateCoordinator,
    WantedDataUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR]


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
        disk_space=DiskSpaceDataUpdateCoordinator(
            hass, entry, host_configuration, lidarr
        ),
        queue=QueueDataUpdateCoordinator(hass, entry, host_configuration, lidarr),
        status=StatusDataUpdateCoordinator(hass, entry, host_configuration, lidarr),
        wanted=WantedDataUpdateCoordinator(hass, entry, host_configuration, lidarr),
        albums=AlbumsDataUpdateCoordinator(hass, entry, host_configuration, lidarr),
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
