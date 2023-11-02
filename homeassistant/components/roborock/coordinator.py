"""Roborock Coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from roborock.cloud_api import RoborockMqttClient
from roborock.containers import DeviceData, HomeDataDevice, HomeDataProduct, NetworkInfo
from roborock.exceptions import RoborockException
from roborock.local_api import RoborockLocalClient
from roborock.roborock_typing import DeviceProp

from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
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
        cloud_api: RoborockMqttClient | None = None,
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
        self.cloud_api = cloud_api
        self.device_info = DeviceInfo(
            name=self.roborock_device_info.device.name,
            identifiers={(DOMAIN, self.roborock_device_info.device.duid)},
            manufacturer="Roborock",
            model=self.roborock_device_info.product.model,
            sw_version=self.roborock_device_info.device.fv,
        )

        if mac := self.roborock_device_info.network_info.mac:
            self.device_info[ATTR_CONNECTIONS] = {(dr.CONNECTION_NETWORK_MAC, mac)}

    async def verify_api(self) -> None:
        """Verify that the api is reachable. If it is not, switch clients."""
        try:
            await self.api.ping()
        except RoborockException:
            if isinstance(self.api, RoborockLocalClient):
                _LOGGER.warning(
                    "Using the cloud API for device %s. This is not recommended as it can lead to rate limiting. We recommend making your vacuum accessible by your Home Assistant instance",
                    self.roborock_device_info.device.duid,
                )
                # We use the cloud api if the local api fails to connect.
                self.api = self.cloud_api
            # Right now this should never be called if the cloud api is the primary api,
            # but in the future if it is, a new else should be added.

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
