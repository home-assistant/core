"""The Airzone Cloud integration coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from aioairzone_cloud.cloudapi import AirzoneCloudApi
from aioairzone_cloud.exceptions import AirzoneCloudError, TooManyRequests
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AIOAIRZONE_CLOUD_TIMEOUT_SEC, DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class AirzoneUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Airzone Cloud device."""

    def __init__(self, hass: HomeAssistant, airzone: AirzoneCloudApi) -> None:
        """Initialize."""
        self.airzone = airzone

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Update data via library."""
        async with async_timeout.timeout(AIOAIRZONE_CLOUD_TIMEOUT_SEC):
            try:
                await self.airzone.update_webservers(False)
                await self.airzone.update_systems()
                await self.airzone.update_zones()
            except TooManyRequests:
                _LOGGER.error("Too many API requests")
            except AirzoneCloudError as error:
                raise UpdateFailed(error) from error
            return self.airzone.data()
