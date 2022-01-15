"""Tradfri DataUpdateCoordinator."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

import async_timeout
from pytradfri.command import Command
from pytradfri.device import Device
from pytradfri.error import RequestError

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL, TIMEOUT_API

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
        self._exception = None

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

    async def _async_run_observe(self, cmd: Command, device: Device = None) -> None:
        """Run observe in a coroutine."""
        self._exception = None

        try:
            await self.api(cmd)
        except RequestError as err:
            _LOGGER.debug(
                "Observation failed for %s, trying again", device, exc_info=err
            )
            self.update_interval = timedelta(
                seconds=5
            )  # Change interval so we get a swift refresh
            self._exception = err
            await self.async_request_refresh()

    @callback
    def _async_start_observe(
        self, device: Device, exc: Exception | None = None
    ) -> Command:
        """Start observation of device."""
        if exc:
            _LOGGER.debug("Observation failed for %s", device, exc_info=exc)
        return device.observe(
            callback=self._observe_update,
            err_callback=self._async_start_observe,
            duration=0,
        )

    async def _async_update_data(self) -> Device:
        """Fetch data from the gateway for a specific device."""
        if self._exception:
            raise self._exception

        try:
            async with async_timeout.timeout(TIMEOUT_API):
                if not self.data:  # Start subscription
                    cmd = self._async_start_observe(device=self.device)
                    self.hass.async_create_task(
                        self._async_run_observe(cmd, self.device)
                    )

            return self.device

        except RequestError as err:
            raise UpdateFailed(
                f"Error communicating with API: {err}. Try unplugging and replugging your "
                f"IKEA gateway."
            ) from err
