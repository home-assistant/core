"""Imports for coordinator.py."""

import asyncio

from uhooapi import Device
from uhooapi.errors import UhooError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL, UhooConfigEntry


class UhooDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching data from the uHoo API."""

    def __init__(self, hass: HomeAssistant, entry: UhooConfigEntry) -> None:
        """Initialize DataUpdateCoordinator."""
        self.entry = entry
        self.platforms: list[str] = []
        self.user_settings_temp = None

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> dict[str, Device]:
        try:
            await self.entry.runtime_data.login()
            if self.entry.runtime_data.devices:
                await asyncio.gather(
                    *[
                        self.entry.runtime_data.get_latest_data(device_id)
                        for device_id in self.entry.runtime_data.devices
                    ]
                )
            return self.entry.runtime_data.get_devices()
        except TimeoutError as error:
            LOGGER.error("Error communicating with Uhoo API: %s", error)
            raise UpdateFailed from error
        except UhooError as error:
            LOGGER.error("UnauthorizedError occurred: %s", error)
            raise UpdateFailed from error
