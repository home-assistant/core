"""Coordinator module for the LK Systems integration."""

from datetime import timedelta
import logging

import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class LKSystemDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching LK Systems data."""

    def __init__(self, hass, api):
        """Initialize the coordinator."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name="LK Systems",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """Fetch data from the API."""
        try:
            return await self.api.get_main_data()
        except aiohttp.ContentTypeError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
