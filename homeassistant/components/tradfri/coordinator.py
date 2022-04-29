"""Tradfri DataUpdateCoordinator."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from pytradfri.command import Command
from pytradfri.device import Device
from pytradfri.error import RequestError

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

SCAN_INTERVAL = 60  # Interval for updating the coordinator


class TradfriDeviceDataUpdateCoordinator(DataUpdateCoordinator[Device]):
    """Coordinator to manage data for a specific Tradfri device."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        api: Callable[[Command | list[Command]], Any],
        device: Device,
    ) -> None:
        """Initialize device coordinator."""
        self.api = api
        self.device = device
        self._exception: Exception | None = None

        super().__init__(
            hass,
            LOGGER,
            name=f"Update coordinator for {device}",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def set_hub_available(self, available: bool) -> None:
        """Set status of hub."""
        if available != self.last_update_success:
            if not available:
                self.last_update_success = False
            await self.async_request_refresh()

    @callback
    def _observe_update(self, device: Device) -> None:
        """Update the coordinator for a device when a change is detected."""
        self.async_set_updated_data(data=device)

    @callback
    def _exception_callback(self, exc: Exception) -> None:
        """Schedule handling exception.."""
        self.hass.async_create_task(self._handle_exception(exc))

    async def _handle_exception(self, exc: Exception) -> None:
        """Handle observe exceptions in a coroutine."""
        # Store exception so that it gets raised in _async_update_data
        self._exception = exc

        LOGGER.debug(
            "Observation failed for %s, trying again", self.device, exc_info=exc
        )
        # Change interval so we get a swift refresh
        self.update_interval = timedelta(seconds=5)
        await self.async_request_refresh()

    async def _async_update_data(self) -> Device:
        """Fetch data from the gateway for a specific device."""
        try:
            if self._exception:
                exc = self._exception
                self._exception = None  # Clear stored exception
                raise exc
        except RequestError as err:
            raise UpdateFailed(f"Error communicating with API: {err}.") from err

        if not self.data or not self.last_update_success:  # Start subscription
            try:
                cmd = self.device.observe(
                    callback=self._observe_update,
                    err_callback=self._exception_callback,
                    duration=0,
                )
                await self.api(cmd)
            except RequestError as err:
                raise UpdateFailed(f"Error communicating with API: {err}.") from err

            # Reset update interval
            self.update_interval = timedelta(seconds=SCAN_INTERVAL)

        return self.device
