"""Helper and coordinator for refoss."""
from __future__ import annotations

from datetime import timedelta
import logging

from refoss_ha.controller.device import BaseDevice
from refoss_ha.exceptions import DeviceTimeoutError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MAX_ERRORS

_LOGGER = logging.getLogger(__name__)


class DeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Manages polling for state changes from the device."""

    def __init__(self, hass: HomeAssistant, device: BaseDevice) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{device.device_info.dev_name}",
            update_interval=timedelta(seconds=15),
        )
        self.device = device
        self._error_count = 0

    async def _async_update_data(self):
        """Update the state of the device."""
        try:
            await self.device.async_handle_update()
        except DeviceTimeoutError as error:
            self._error_count += 1

            if self.last_update_success and self._error_count >= MAX_ERRORS:
                _LOGGER.debug(
                    "Device is unavailable: %s (%s)",
                    self.name,
                    self.device.device_info,
                )
                raise UpdateFailed(f"Device {self.name} is unavailable") from error
