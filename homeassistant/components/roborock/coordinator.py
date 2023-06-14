"""Roborock Coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from roborock.containers import DeviceData, HomeDataDevice, HomeDataProduct, NetworkInfo
from roborock.exceptions import RoborockException
from roborock.local_api import RoborockLocalClient
from roborock.roborock_typing import DeviceProp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import RoborockHassDeviceInfo

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class RoborockDataUpdateCoordinator(DataUpdateCoordinator[DeviceProp]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: HomeDataDevice,
        device_networking: NetworkInfo,
        product_info: HomeDataProduct,
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.roborock_device_info = RoborockHassDeviceInfo(
            device,
            device_networking,
            product_info,
            DeviceProp(),
        )
        device_data = DeviceData(device, product_info.model, device_networking.ip)
        self.api = RoborockLocalClient(device_data)
        self.device_info = DeviceInfo(
            name=self.roborock_device_info.device.name,
            identifiers={(DOMAIN, self.roborock_device_info.device.duid)},
            manufacturer="Roborock",
            model=self.roborock_device_info.product.model,
            sw_version=self.roborock_device_info.device.fv,
        )

    async def release(self) -> None:
        """Disconnect from API."""
        await self.api.async_disconnect()

    async def _update_device_prop(self) -> None:
        """Update device properties."""
        device_prop = await self.api.get_prop()
        if device_prop:
            if self.roborock_device_info.props:
                self.roborock_device_info.props.update(device_prop)
            else:
                self.roborock_device_info.props = device_prop

    async def _async_update_data(self) -> DeviceProp:
        """Update data via library."""
        try:
            await self._update_device_prop()
        except RoborockException as ex:
            raise UpdateFailed(ex) from ex
        return self.roborock_device_info.props
