"""Roborock Coordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from roborock.containers import (
    HomeDataDevice,
    HomeDataProduct,
    NetworkInfo,
    RoborockLocalDeviceInfo,
)
from roborock.exceptions import RoborockException
from roborock.local_api import RoborockLocalClient
from roborock.typing import RoborockDeviceProp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import RoborockHassDeviceInfo

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class RoborockDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, RoborockDeviceProp]]
):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        devices: list[HomeDataDevice],
        devices_networking: dict[str, NetworkInfo],
        product_info: dict[str, HomeDataProduct],
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        local_devices_info: dict[str, RoborockLocalDeviceInfo] = {}
        hass_devices_info: dict[str, RoborockHassDeviceInfo] = {}
        for device in devices:
            if not (networking := devices_networking.get(device.duid)):
                _LOGGER.warning("Device %s is offline and cannot be setup", device.duid)
                continue
            hass_devices_info[device.duid] = RoborockHassDeviceInfo(
                device,
                networking,
                product_info[device.product_id],
                RoborockDeviceProp(),
            )
            local_devices_info[device.duid] = RoborockLocalDeviceInfo(
                device, networking
            )
        self.api = RoborockLocalClient(local_devices_info)
        self.devices_info = hass_devices_info

    async def release(self) -> None:
        """Disconnect from API."""
        await self.api.async_disconnect()

    async def _update_device_prop(self, device_info: RoborockHassDeviceInfo) -> None:
        """Update device properties."""
        device_prop = await self.api.get_prop(device_info.device.duid)
        if device_prop:
            if device_info.props:
                device_info.props.update(device_prop)
            else:
                device_info.props = device_prop

    async def _async_update_data(self) -> dict[str, RoborockDeviceProp]:
        """Update data via library."""
        try:
            await asyncio.gather(
                *(
                    self._update_device_prop(device_info)
                    for device_info in self.devices_info.values()
                )
            )
        except RoborockException as ex:
            raise UpdateFailed(ex) from ex
        return {
            device_id: device_info.props
            for device_id, device_info in self.devices_info.items()
        }
