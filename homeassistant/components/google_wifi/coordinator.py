"""DataUpdateCoordinator for the Google Wifi integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GoogleWifiUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Google Wifi API."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize the coordinator."""
        self.host = host
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """Fetch data from the router via HTTP."""
        url = f"http://{self.host}/api/v1/status"
        try:
            # We use hass.async_add_executor_job because 'requests' is synchronous
            async with asyncio.timeout(10):
                response = await self.hass.async_add_executor_job(requests.get, url)
            return response.json()
        except requests.exceptions.RequestException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
