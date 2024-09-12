"""Coordinator for Axion Lighting integration."""

from datetime import timedelta
from typing import Any

from requests.exceptions import RequestException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER


class AxionDataUpdateCoordinator(DataUpdateCoordinator):
    """Custom coordinator for Axion Lighting integration."""

    def __init__(self, hass: HomeAssistant, api: Any, channel: int) -> None:
        """Initialize the Axion data coordinator."""
        self.api = api
        self.channel = channel
        super().__init__(
            hass,
            _LOGGER,
            name="Axion Light",
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> Any:
        """Fetch data from the API endpoint."""
        try:
            return await self.api.get_level(self.channel)
        except RequestException as err:
            raise UpdateFailed("Error communicating with API") from err
