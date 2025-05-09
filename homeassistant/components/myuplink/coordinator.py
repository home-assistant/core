"""Coordinator for myUplink."""

import asyncio.timeouts
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from myuplink import Device, DevicePoint, MyUplinkAPI, System

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class CoordinatorData:
    """Represent coordinator data."""

    systems: list[System]
    devices: dict[str, Device]
    points: dict[str, dict[str, DevicePoint]]
    time: datetime


type MyUplinkConfigEntry = ConfigEntry[MyUplinkDataCoordinator]


class MyUplinkDataCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinator for myUplink data."""

    config_entry: MyUplinkConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: MyUplinkConfigEntry, api: MyUplinkAPI
    ) -> None:
        """Initialize myUplink coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="myuplink",
            update_interval=timedelta(seconds=60),
        )
        self.api = api

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from the myUplink API."""
        async with asyncio.timeout(10):
            # Get systems
            systems = await self.api.async_get_systems()

            devices: dict[str, Device] = {}
            points: dict[str, dict[str, DevicePoint]] = {}
            device_ids = [
                device.deviceId for system in systems for device in system.devices
            ]
            for device_id in device_ids:
                # Get device info
                api_device_info = await self.api.async_get_device(device_id)
                devices[device_id] = api_device_info

                # Get device points (data)
                api_device_points = await self.api.async_get_device_points(device_id)
                point_info: dict[str, DevicePoint] = {}
                for point in api_device_points:
                    point_info[point.parameter_id] = point

                points[device_id] = point_info

            return CoordinatorData(
                systems=systems, devices=devices, points=points, time=datetime.now()
            )
