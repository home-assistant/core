"""Roborock Coordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from roborock.code_mappings import ModelSpecification
from roborock.containers import (
    HomeDataDevice,
    HomeDataProduct,
    NetworkInfo,
    RoborockLocalDeviceInfo,
)
from roborock.exceptions import RoborockException
from roborock.local_api import RoborockLocalClient
from roborock.roborock_typing import DeviceProp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import RoborockHassDeviceInfo

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class RoborockDataUpdateCoordinator(DataUpdateCoordinator[dict[str, DeviceProp]]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        devices: list[HomeDataDevice],
        devices_networking: dict[str, NetworkInfo],
        product_info: dict[str, HomeDataProduct],
        model_specifications: dict[str, ModelSpecification],
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        hass_devices_info: dict[str, RoborockHassDeviceInfo] = {}
        self.api_map: dict[str, RoborockLocalClient] = {}
        for device in devices:
            if not (networking := devices_networking.get(device.duid)):
                _LOGGER.warning("Device %s is offline and cannot be setup", device.duid)
                continue
            model_specification = model_specifications[device.product_id]
            hass_devices_info[device.duid] = RoborockHassDeviceInfo(
                device,
                networking,
                product_info[device.product_id],
                DeviceProp(),
                model_specification,
            )
            device_info = RoborockLocalDeviceInfo(
                device, model_specification, networking
            )
            self.api_map[device.duid] = RoborockLocalClient(device_info)
        self.devices_info = hass_devices_info

    async def release(self) -> None:
        """Disconnect from API."""
        await asyncio.gather(*(api.async_disconnect() for api in self.api_map.values()))

    async def _update_device_prop(self, device_info: RoborockHassDeviceInfo) -> None:
        """Update device properties."""
        device_prop = await self.api_map[device_info.device.duid].get_prop()
        if device_prop:
            if device_info.props:
                device_info.props.update(device_prop)
            else:
                device_info.props = device_prop

    async def _async_update_data(self) -> dict[str, DeviceProp]:
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
