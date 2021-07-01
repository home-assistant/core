"""Provides the ezviz DataUpdateCoordinator."""
from datetime import timedelta
import logging

from async_timeout import timeout
from pyezviz.exceptions import HTTPError, InvalidURL, PyEzvizError

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EzvizDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Ezviz data."""

    def __init__(self, hass, *, api):
        """Initialize global Ezviz data updater."""
        self.ezviz_client = api
        update_interval = timedelta(seconds=30)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    def _update_data(self):
        """Fetch data from Ezviz via camera load function."""
        cameras = self.ezviz_client.load_cameras()

        return cameras

    async def _async_update_data(self):
        """Fetch data from Ezviz."""
        try:
            async with timeout(35):
                return await self.hass.async_add_executor_job(self._update_data)

        except (InvalidURL, HTTPError, PyEzvizError) as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
