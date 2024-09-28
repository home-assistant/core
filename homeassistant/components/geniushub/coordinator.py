"""Define a coordinator to fetch data from the Genius Hub API."""

import logging

from geniushubclient import GeniusHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GeniusHubCoordinator(DataUpdateCoordinator[None]):
    """Define an object to coordinate fetching Genius Hub data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: GeniusHub, unique_id: str) -> None:
        """Initialize the Genius Hub coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Genius Hub",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.unique_id = unique_id

    async def _async_update_data(self) -> None:
        return await self.client.update()
