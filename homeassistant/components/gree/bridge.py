"""Helper and wrapper classes for Gree module."""
from typing import List

from greeclimate.device import Device, DeviceInfo
from greeclimate.discovery import Discovery
from greeclimate.exceptions import DeviceNotBoundError

from homeassistant import exceptions


class DeviceHelper:
    """Device search and bind wrapper for Gree platform."""

    @staticmethod
    async def try_bind_device(device_info: DeviceInfo) -> Device:
        """Try and bing with a discovered device.

        Note the you must bind with the device very quickly after it is discovered, or the
        process may not be completed correctly, raising a `CannotConnect` error.
        """
        device = Device(device_info)
        try:
            await device.bind()
        except DeviceNotBoundError as exception:
            raise CannotConnect from exception
        return device

    @staticmethod
    async def find_devices() -> List[DeviceInfo]:
        """Gather a list of device infos from the local network."""
        return await Discovery.search_devices()


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
