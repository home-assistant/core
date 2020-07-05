"""Helper and wrapper classes for Gree module."""
import logging
import socket
from typing import List

from greeclimate.device import Device
from greeclimate.device_info import DeviceInfo
from greeclimate.exceptions import DeviceNotBoundError
from greeclimate.gree_climate import GreeClimate

from homeassistant import exceptions

_LOGGER = logging.getLogger(__name__)


class DeviceHelper:
    """Device search and bind wrapper for Gree platform."""

    @staticmethod
    async def try_bind_device(device_info: DeviceInfo) -> Device:
        """Try and bing with a discovered device.

        Note the you must bind with the device very quickly after it is discovered, or the
        process may not be completed correctly, raising a `CannotConnect` error.
        """
        try:
            device = Device(device_info)
            await device.bind()
            return device
        except DeviceNotBoundError:
            raise CannotConnect

    @staticmethod
    async def find_devices() -> List[DeviceInfo]:
        """Gather a list of device infos from the local network."""
        gree = GreeClimate()
        return await gree.search_devices()

    @staticmethod
    def get_ip(host: str) -> str:
        """Get ip from hostname."""
        if host is None:
            return None
        return socket.gethostbyname(host)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
