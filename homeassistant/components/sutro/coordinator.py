"""Data update coordinator for the Sutro integration."""
from datetime import timedelta
import logging

import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .sutro_api import SutroApi

_LOGGER = logging.getLogger(__name__)


class SutroDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific Sutro device."""

    def __init__(self, hass: HomeAssistant, sutro_api: SutroApi) -> None:
        """Initialize data update coordinator for Sutro device."""
        super().__init__(
            hass,
            _LOGGER,
            name="Sutro",
            update_interval=timedelta(seconds=30),
        )
        self.sutro_api = sutro_api

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        async with async_timeout.timeout(10):
            await self.sutro_api.async_get_info()
