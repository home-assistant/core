"""Coordinator for TheSilentWave integration."""

from datetime import timedelta
import logging

import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class TheSilentWaveCoordinator(DataUpdateCoordinator):
    """Class to manage fetching the data from the API."""

    def __init__(self, hass, name, url, scan_interval):
        """Initialize the coordinator."""
        self._name = name
        self._url = url
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Fetch data from the API."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self._url) as response:
                    response.raise_for_status()
                    data = await response.text()
                    # Convert "1" to "on" and "0" to "off"
                    return "on" if data.strip() == "1" else "off"
            except aiohttp.ClientError as err:
                raise UpdateFailed(f"Error fetching data from API: {err}") from err
