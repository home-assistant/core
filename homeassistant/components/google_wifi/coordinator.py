"""DataUpdateCoordinator for the Google Wifi integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GoogleWifiUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Google Wifi API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            config_entry=entry
        )

    async def _async_update_data(self):
        """Fetch data from the router via HTTP."""
        # Pull the host directly from the entry data every time
        host = self.entry.data[CONF_IP_ADDRESS]
        url = f"http://{host}/api/v1/status"

        try:
            # We use hass.async_add_executor_job because 'requests' is synchronous
            # Pass an explicit timeout to the synchronous requests call
            # and wrap it in the executor job
            response = await self.hass.async_add_executor_job(
                lambda: requests.get(url, timeout=5)
            )

            # Ensure we got a 200 OK before attempting to parse
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as err:
            # This catches timeouts, connection errors, and 4xx/5xx responses
            raise UpdateFailed(f"Error communicating with router: {err}") from err
        except ValueError as err:
            # Catches cases where the response isn't valid JSON
            raise UpdateFailed(f"Invalid JSON received from router: {err}") from err
