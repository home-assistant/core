"""DataUpdateCoordinator for Plugwise."""
from datetime import timedelta

import async_timeout
from plugwise import Smile
from plugwise.exceptions import XMLDataMissingError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DEFAULT_TIMEOUT, DOMAIN, LOGGER


class PlugwiseDataUpdateCoordinator(DataUpdateCoordinator[bool]):
    """Class to manage fetching Plugwise data from single endpoint."""

    def __init__(self, hass: HomeAssistant, api: Smile) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=api.smile_name or DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL.get(
                str(api.smile_type), timedelta(seconds=60)
            ),
        )
        self.api = api

    async def _async_update_data(self) -> bool:
        """Fetch data from Plugwise."""
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                await self.api.full_update_device()
        except XMLDataMissingError as err:
            raise UpdateFailed("Smile update failed") from err
        return True
