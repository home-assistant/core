"""Coordinator for Axion Lighting integration."""

from datetime import timedelta
from typing import Any

from libaxion_dmx import AxionDmxApi
from requests.exceptions import RequestException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER


class AxionDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Custom coordinator for Axion Lighting integration."""

    def __init__(self, hass: HomeAssistant, api: AxionDmxApi, channel: int) -> None:
        """Initialize the Axion data coordinator."""
        self.api = api
        self.channel = channel
        super().__init__(
            hass,
            _LOGGER,
            name="Axion Light",
            update_interval=timedelta(seconds=1),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API endpoint."""
        try:
            # Return data in dictionary form
            return await self.api.get_level(self.channel - 1)
        except RequestException as err:
            raise UpdateFailed("Error communicating with API") from err
