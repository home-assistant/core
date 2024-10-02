"""Data coordinator for the ezbeq Profile Loader integration."""

from datetime import timedelta
import logging

from httpx import HTTPStatusError, RequestError
from pyezbeq.errors import DeviceInfoEmpty
from pyezbeq.ezbeq import EzbeqClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# circular dependency if imported
type EzBEQConfigEntry = ConfigEntry[EzBEQCoordinator]


class EzBEQCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching ezbeq data."""

    config_entry: EzBEQConfigEntry

    def __init__(self, hass: HomeAssistant, client: EzbeqClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ezbeq",
            update_interval=timedelta(seconds=30),
        )
        self.client = client

    async def _async_update_data(self):
        """Fetch data from the ezbeq API."""
        try:
            await self.client.get_status()
            await self.client.get_version()
        except (DeviceInfoEmpty, HTTPStatusError, RequestError) as err:
            _LOGGER.error("Error fetching ezbeq data: %s", err)
            raise
