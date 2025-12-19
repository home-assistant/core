"""Imports for coordinator.py."""

import asyncio

from uhooapi import Client, Device

from homeassistant import core
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL


class UhooDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the uHoo API."""

    def __init__(self, hass: core.HomeAssistant, client: Client) -> None:
        """Initialize DataUpdateCoordinator."""
        self.client = client
        self.platforms: list[str] = []
        self.user_settings_temp = None

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> dict[str, Device]:
        try:
            await self.client.login()
            if self.client.devices:
                await asyncio.gather(
                    *[
                        self.client.get_latest_data(device_id)
                        for device_id in self.client.devices
                    ]
                )
            return self.client.get_devices()
        except Exception as exception:
            LOGGER.error(
                f"Error: an exception occurred while attempting to get latest data: {exception}"
            )
            raise UpdateFailed from exception
