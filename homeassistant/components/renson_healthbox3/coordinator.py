"""DataUpdateCoordinator for Renson."""
import asyncio
from datetime import timedelta

from pyhealthbox3.healthbox3 import Healthbox3

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER


class RensonCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Renson."""

    def __init__(
        self,
        name: str,
        hass: HomeAssistant,
        api: Healthbox3,
        update_interval=timedelta(seconds=30),
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            # Name of the data. For logging purposes.
            name=name,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=update_interval,
        )

        self.api = api

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        async with asyncio.timeout(30):
            return await self.api.async_get_data()
