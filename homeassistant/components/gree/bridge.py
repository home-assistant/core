"""Helper and wrapper classes for Gree module."""
from datetime import timedelta
import logging

from greeclimate.device import Device
from greeclimate.exceptions import DeviceTimeoutError

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

            if not self.last_update_success and self._error_count:
                _LOGGER.warning(
                    "Device is available: %s (%s)",
                    self.name,
                    str(self.device.device_info),
                )

            self._error_count = 0
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
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown exception caught while sending state update to: %s (%s)",
                self.name,
                self.device.device_info,
            )

    @property
    def device_info(self):
        """Return the gree device information."""
        return self._device.device_info
