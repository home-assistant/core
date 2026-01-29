"""Provides the imou DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

# Update interval for cloud polling (60 seconds minimum for cloud services)
SCAN_INTERVAL = timedelta(seconds=60)


class ImouDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for Imou devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_manager: ImouHaDeviceManager,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Imou data update coordinator.

        Args:
            hass: Home Assistant core object
            device_manager: Imou device manager
            config_entry: Configuration entry
        """
        _LOGGER.debug("Coordinator initialized")
        # Integration determines update interval, not user-configurable
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
        self._unavailable_logged: bool = False

    @property
    def devices(self) -> list[ImouHaDevice]:
        """Return the list of devices.

        Returns:
            List of Imou device objects
        """
        return self._devices

    @property
    def device_manager(self) -> ImouHaDeviceManager:
        """Return the device manager.

        Returns:
            Imou device manager instance
        """
        return self._device_manager

    async def _async_setup(self) -> None:
        """Set up the coordinator.

        This method is called automatically during
        coordinator.async_config_entry_first_refresh to load data
        that only needs to be loaded once.
        """
        self._devices = await self._device_manager.async_get_devices()

    async def async_update_all_device(self) -> None:
        """Update all device statuses.

        Updates the status of all devices in parallel using asyncio.gather.
        """
        await asyncio.gather(
            *[
                self._device_manager.async_update_device_status(device)
                for device in self._devices
            ],
            return_exceptions=True,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update coordinator data.

        Raises:
            UpdateFailed: If data fetching fails
        """
        _LOGGER.debug("Updating coordinator data")
        async with asyncio.timeout(300):
            try:
                await self.async_update_all_device()
            except TimeoutError as err:
                if not self._unavailable_logged:
                    _LOGGER.info(
                        "Imou devices are unavailable: Timeout while fetching data"
                    )
                    self._unavailable_logged = True
                raise UpdateFailed("Timeout while fetching data: {err}") from err
            except Exception as err:
                if not self._unavailable_logged:
                    _LOGGER.info("Imou devices are unavailable: %s", err)
                    self._unavailable_logged = True
                raise UpdateFailed(f"Error updating Imou devices: {err}") from err
            # Update successful, log recovery if needed
            if self._unavailable_logged:
                _LOGGER.info("Imou devices are back online")
                self._unavailable_logged = False
        # Return empty dict since we don't need to store data
        return {}
