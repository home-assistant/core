"""The myUplink integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

import async_timeout
from myuplink.api import MyUplinkAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    device_registry as dr,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import api
from .const import (
    DOMAIN,
    MU_DATAGROUP_DEVICES,
    MU_DATAGROUP_POINTS,
    MU_DATAGROUP_SYSTEMS,
    MU_DATATIME,
    MU_DEVICE_CONNECTIONSTATE,
    MU_DEVICE_FIRMWARE_CURRENT,
    MU_DEVICE_FIRMWARE_DESIRED,
    MU_DEVICE_PRODUCTNAME,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up myUplink from a config entry."""

    hass.data[DOMAIN] = {}

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, implementation)

    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    # setup MyUplinkAPI and coordinator for data fetch
    mu_api = MyUplinkAPI(auth)
    mu_coordinator = MyUplinkDataCoordinator(hass, mu_api)

    await mu_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = {
        "api": mu_api,
        "coordinator": mu_coordinator,
    }

    await update_all_devices(hass, config_entry, mu_coordinator)

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_all_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, coordinator: MyUplinkDataCoordinator
):
    """Update all devices."""
    mu_devices = coordinator.data[MU_DATAGROUP_DEVICES]

    device_registry = dr.async_get(hass)

    for device_id in mu_devices:
        device_data = mu_devices[device_id]

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, device_id)},
            name=device_data[MU_DEVICE_PRODUCTNAME],
            manufacturer=device_data[MU_DEVICE_PRODUCTNAME].split(" ")[0],
            model=device_data[MU_DEVICE_PRODUCTNAME],
            sw_version=device_data[MU_DEVICE_FIRMWARE_CURRENT],
        )


class MyUplinkDataCoordinator(DataUpdateCoordinator):
    """Coordinator for myUplink data."""

    def __init__(self, hass: HomeAssistant, mu_api: MyUplinkAPI) -> None:
        """Initialize myUplink coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="myuplink",
            update_interval=timedelta(seconds=30),
        )
        self.mu_api = mu_api

    async def _async_update_data(self):
        """Fetch data from the myUplink API."""
        async with async_timeout.timeout(10):
            mu_data = {}
            mu_systems = await self.mu_api.async_get_systems()

            mu_devices = {}
            mu_points = {}
            for system in mu_systems:
                for device in system.devices:

                    # Get device info
                    api_device_info = await self.mu_api.async_get_device(
                        device.deviceId
                    )
                    mu_device_info = {}
                    mu_device_info[
                        MU_DEVICE_FIRMWARE_CURRENT
                    ] = api_device_info.firmwareCurrent

                    mu_device_info[
                        MU_DEVICE_FIRMWARE_DESIRED
                    ] = api_device_info.firmwareDesired

                    mu_device_info[
                        MU_DEVICE_CONNECTIONSTATE
                    ] = api_device_info.connectionState

                    mu_device_info[MU_DEVICE_PRODUCTNAME] = api_device_info.productName
                    mu_devices[device.deviceId] = mu_device_info

                    # Get device points (data)
                    api_device_points = await self.mu_api.async_get_device_points(
                        device.deviceId
                    )
                    mu_point_info = {}
                    for point in api_device_points:
                        mu_point_info[point.parameter_id] = point

                    mu_points[device.deviceId] = mu_point_info

            mu_data[MU_DATAGROUP_SYSTEMS] = mu_systems
            mu_data[MU_DATAGROUP_DEVICES] = mu_devices
            mu_data[MU_DATAGROUP_POINTS] = mu_points
            mu_data[MU_DATATIME] = datetime.now()

            return mu_data
