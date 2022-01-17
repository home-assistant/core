"""Tradfri DataUpdateCoordinator."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from pytradfri.command import Command
from pytradfri.device import Device
from pytradfri.error import RequestError

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TradfriDeviceDataUpdateCoordinator(DataUpdateCoordinator):
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
            _LOGGER,
            name=f"Update coordinator for {device}",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    @callback
    def _observe_update(self, device: Device) -> None:
        """Update the coordinator for a device when a change is detected."""
        self.update_interval = timedelta(seconds=SCAN_INTERVAL)  # Reset update interval

        self.async_set_updated_data(data=device)

    @callback
    def _exception_callback(self, device: Device, exc: Exception | None = None) -> None:
        """Schedule handling exception.."""
        self.hass.async_create_task(self._handle_exception(device=device, exc=exc))

    async def _handle_exception(
        self, device: Device, exc: Exception | None = None
    ) -> None:
        """Handle observe exceptions in a coroutine."""
        self._exception = (
            exc  # Store exception so that it gets raised in _async_update_data
        )

        _LOGGER.debug("Observation failed for %s, trying again", device, exc_info=exc)
        self.update_interval = timedelta(
            seconds=5
        )  # Change interval so we get a swift refresh
        await self.async_request_refresh()

    async def _async_update_data(self) -> Device:
        """Fetch data from the gateway for a specific device."""
        try:
            if self._exception:
                exc = self._exception
                self._exception = None  # Clear stored exception
                raise exc  # pylint: disable-msg=raising-bad-type
        except RequestError as err:
            raise UpdateFailed(
                f"Error communicating with API: {err}. Try unplugging and replugging your "
                f"IKEA gateway."
            ) from err

        if not self.data:  # Start subscription
            try:
                cmd = self.device.observe(
                    callback=self._observe_update,
                    err_callback=self._exception_callback,
                    duration=0,
                )
                await self.api(cmd)
            except RequestError as exc:
                await self._handle_exception(device=self.device, exc=exc)

        return self.device
