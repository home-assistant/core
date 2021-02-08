"""Helper and wrapper classes for Gree module."""
from datetime import timedelta
import logging
from typing import List

from greeclimate.device import Device, DeviceInfo
from greeclimate.discovery import Discovery
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError

from homeassistant import exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MAX_ERRORS

_LOGGER = logging.getLogger(__name__)


class DeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Manages polling for state changes from the device."""

    def __init__(self, hass: HomeAssistant, device: Device):
        """Initialize the data update coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{device.device_info.name}",
            update_interval=timedelta(seconds=60),
        )
        self.device = device
        self._error_count = 0

    async def _async_update_data(self):
        """Update the state of the device."""
        try:
            await self.device.update_state()
        except DeviceTimeoutError as error:
            self._error_count += 1

            # Under normal conditions GREE units timeout every once in a while
            if self.last_update_success and self._error_count >= MAX_ERRORS:
                _LOGGER.warning(
                    "Device is unavailable: %s (%s)",
                    self.name,
                    self.device.device_info,
                )
                raise UpdateFailed(error) from error
        else:
            if not self.last_update_success and self._error_count:
                _LOGGER.warning(
                    "Device is available: %s (%s)",
                    self.name,
                    str(self.device.device_info),
                )

            self._error_count = 0

    async def push_state_update(self):
        """Send state updates to the physical device."""
        try:
            return await self.device.push_state_update()
        except DeviceTimeoutError:
            _LOGGER.warning(
                "Timeout send state update to: %s (%s)",
                self.name,
                self.device.device_info,
            )


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
