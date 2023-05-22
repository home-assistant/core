"""Coordinator for myUplink."""
from datetime import datetime, timedelta
import logging

import async_timeout
from myuplink.api import MyUplinkAPI
from myuplink.models import DevicePoint

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
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


class MyUplinkDataCoordinator(DataUpdateCoordinator):
    """Coordinator for myUplink data."""

    def __init__(self, hass: HomeAssistant, mu_api: MyUplinkAPI) -> None:
        """Initialize myUplink coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="myuplink",
            update_interval=timedelta(seconds=60),
        )
        self.mu_api = mu_api

    async def _async_update_data(self):
        """Fetch data from the myUplink API."""
        async with async_timeout.timeout(10):
            _LOGGER.debug("Coordinator preparing updating")

            data: dict[str, any] = {}

            # Get systems
            mu_systems = await self.mu_api.async_get_systems()
            data[MU_DATAGROUP_SYSTEMS] = mu_systems

            # Get device info
            devices: dict[str, dict[str, str]] = {}
            device_ids = await self.get_system_device_ids()
            for device_id in device_ids:
                api_device_info = await self.mu_api.async_get_device(device_id)
                device_info: dict[str, str] = {}
                device_info[
                    MU_DEVICE_FIRMWARE_CURRENT
                ] = api_device_info.firmwareCurrent
                device_info[
                    MU_DEVICE_FIRMWARE_DESIRED
                ] = api_device_info.firmwareDesired
                device_info[MU_DEVICE_CONNECTIONSTATE] = api_device_info.connectionState
                device_info[MU_DEVICE_PRODUCTNAME] = api_device_info.productName
                devices[device_id] = device_info

            # Get device points (data)
            points: dict[str, dict[str, DevicePoint]] = {}
            for device_id in device_ids:
                api_device_points = await self.mu_api.async_get_device_points(device_id)
                point_info: dict[str, DevicePoint] = {}
                for point in api_device_points:
                    point_info[point.parameter_id] = point

                points[device_id] = point_info

            # Store data
            data[MU_DATAGROUP_DEVICES] = devices
            data[MU_DATAGROUP_POINTS] = points
            data[MU_DATATIME] = datetime.now()

            _LOGGER.debug("Data in coordinator is updated")

            return data

    async def get_system_device_ids(self) -> list[str]:
        """Load system devices from API."""
        systems = await self.mu_api.async_get_systems()

        id_list: list[str] = []
        for sys in systems:
            for device in sys.devices:
                id_list.append(device.deviceId)

        return id_list
