"""Coordinator for the LetPot integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from letpot.deviceclient import LetPotDeviceClient
from letpot.exceptions import LetPotException
from letpot.models import AuthenticationInfo, LetPotDevice, LetPotDeviceStatus

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import REQUEST_UPDATE_TIMEOUT

if TYPE_CHECKING:
    from . import LetPotConfigEntry

_LOGGER = logging.getLogger(__name__)


class LetPotDeviceCoordinator(DataUpdateCoordinator[LetPotDeviceStatus]):
    """Class to handle data updates for a specific garden."""

    config_entry: LetPotConfigEntry

    device: LetPotDevice
    deviceclient: LetPotDeviceClient
    _update_event: asyncio.Event | None = None
    _subscription: asyncio.Task | None = None

    def __init__(
        self, hass: HomeAssistant, info: AuthenticationInfo, device: LetPotDevice
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"LetPot {device.serial_number}",
        )
        self._info = info
        self.device = device
        self.deviceclient = LetPotDeviceClient(info, device.serial_number)

    def _handle_status_update(self, status: LetPotDeviceStatus) -> None:
        """Distribute status update to entities."""
        self.async_set_updated_data(data=status)
        if self._update_event is not None and not self._update_event.is_set():
            self._update_event.set()

    async def _async_update_data(self) -> LetPotDeviceStatus:
        """Request an update from the device and wait for a status update or timeout."""
        self._update_event = asyncio.Event()

        try:
            async with asyncio.timeout(REQUEST_UPDATE_TIMEOUT):
                if self._subscription is None or self._subscription.done():
                    # Set up the subscription, which will request a status update when connected
                    self._subscription = self.config_entry.async_create_background_task(
                        hass=self.hass,
                        target=self.deviceclient.subscribe(self._handle_status_update),
                        name=f"{self.device.serial_number}_subscription_task",
                    )
                else:
                    # Request an update, existing subscription will receive status update
                    await self.deviceclient.request_status_update()

                await self._update_event.wait()
        except LetPotException as exc:
            raise UpdateFailed(exc) from exc

        # The subscription task will have updated coordinator.data, so return that data.
        # If we don't return anything here, coordinator.data will be set to None.
        return self.data
