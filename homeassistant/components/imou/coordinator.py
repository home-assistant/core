"""Provides the Imou DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

type ImouConfigEntry = ConfigEntry[ImouDataUpdateCoordinator]


class ImouDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for Imou devices."""

    config_entry: ImouConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        device_manager: ImouHaDeviceManager,
        config_entry: ImouConfigEntry,
    ) -> None:
        """Initialize the Imou data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ImouDataUpdateCoordinator",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
            always_update=True,
        )
        self._device_manager = device_manager
        self._devices: list[ImouHaDevice] = []

    @property
    def devices(self) -> list[ImouHaDevice]:
        """Return the list of devices."""
        return self._devices

    @property
    def device_manager(self) -> ImouHaDeviceManager:
        """Return the device manager."""
        return self._device_manager

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        self._devices = await self._device_manager.async_get_devices()

    async def _async_update_data(self) -> None:
        """Update coordinator data."""
        async with asyncio.timeout(300):
            try:
                await asyncio.gather(
                    *[
                        self._device_manager.async_update_device_status(device)
                        for device in self._devices
                    ],
                    return_exceptions=True,
                )
            except TimeoutError as err:
                raise UpdateFailed(f"Timeout while fetching data: {err}") from err
            except Exception as err:
                raise UpdateFailed(f"Error updating Imou devices: {err}") from err
