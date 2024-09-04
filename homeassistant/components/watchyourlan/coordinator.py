"""Coordinator for the WatchYourLAN integration."""

import asyncio
from asyncio import timeout
from datetime import timedelta
import logging

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class WatchYourLANUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the WatchYourLAN API."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize the coordinator."""
        update_interval = timedelta(
            minutes=config.get("update_interval", 5)
        )  # Use configured update interval
        super().__init__(
            hass,
            _LOGGER,
            name="WatchYourLAN",
            update_interval=update_interval,
        )
        self.api_url = config["url"]

    async def _async_update_data(self):
        """Fetch data from the WatchYourLAN API with retries."""
        retries = 3
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with timeout(10):
                        response = await session.get(f"{self.api_url}/api/all")
                        if response.status != 200:
                            raise UpdateFailed(  # noqa: TRY301
                                f"Error fetching data: {response.status}"
                            )
                        return await response.json()

            except Exception as e:
                if attempt < retries - 1:
                    _LOGGER.warning(
                        "Retrying after failed attempt to fetch data from WatchYourLAN: %s",
                        e,
                    )
                    await asyncio.sleep(2)
                else:
                    _LOGGER.error(
                        "Failed to fetch data from WatchYourLAN after %s attempts: %s",
                        retries,
                        e,
                    )
                    raise UpdateFailed(f"Error fetching data: {e}") from e

        return None
