"""Helper and coordinator for refoss."""
from __future__ import annotations

from datetime import timedelta

from refoss_ha.controller.device import BaseDevice
from refoss_ha.exceptions import DeviceTimeoutError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import _LOGGER, DOMAIN, MAX_ERRORS


class RefossDataUpdateCoordinator(DataUpdateCoordinator[None]):
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

    async def _async_update_data(self) -> None:
        """Update the state of the device."""
        try:
            await self.device.async_handle_update()
            self.last_update_success = True
            self._error_count = 0
        except DeviceTimeoutError:
            self._error_count += 1

            if self._error_count >= MAX_ERRORS:
                self.last_update_success = False
