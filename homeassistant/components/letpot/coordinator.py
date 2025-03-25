"""Coordinator for the LetPot integration."""

from __future__ import annotations

import asyncio
import logging

from letpot.deviceclient import LetPotDeviceClient
from letpot.exceptions import LetPotAuthenticationException, LetPotException
from letpot.models import AuthenticationInfo, LetPotDevice, LetPotDeviceStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import REQUEST_UPDATE_TIMEOUT

_LOGGER = logging.getLogger(__name__)

type LetPotConfigEntry = ConfigEntry[list[LetPotDeviceCoordinator]]


class LetPotDeviceCoordinator(DataUpdateCoordinator[LetPotDeviceStatus]):
    """Class to handle data updates for a specific garden."""

    config_entry: LetPotConfigEntry

    device: LetPotDevice
    device_client: LetPotDeviceClient

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LetPotConfigEntry,
        info: AuthenticationInfo,
        device: LetPotDevice,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"LetPot {device.serial_number}",
        )
        self._info = info
        self.device = device
        self.device_client = LetPotDeviceClient(info, device.serial_number)

    def _handle_status_update(self, status: LetPotDeviceStatus) -> None:
        """Distribute status update to entities."""
        self.async_set_updated_data(data=status)

    async def _async_setup(self) -> None:
        """Set up subscription for coordinator."""
        try:
            await self.device_client.subscribe(self._handle_status_update)
        except LetPotAuthenticationException as exc:
            raise ConfigEntryAuthFailed from exc

    async def _async_update_data(self) -> LetPotDeviceStatus:
        """Request an update from the device and wait for a status update or timeout."""
        try:
            async with asyncio.timeout(REQUEST_UPDATE_TIMEOUT):
                await self.device_client.get_current_status()
        except LetPotException as exc:
            raise UpdateFailed(exc) from exc

        # The subscription task will have updated coordinator.data, so return that data.
        # If we don't return anything here, coordinator.data will be set to None.
        return self.data
