"""Coordinator for the WatchYourLAN integration."""

from datetime import timedelta
import logging
from typing import Any

from httpx import ConnectError, HTTPStatusError
from watchyourlanclient import WatchYourLANClient

from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class WatchYourLANUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching data from the WatchYourLAN API."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        # Set up a regular polling interval (e.g., every 60 seconds)
        update_interval = timedelta(seconds=60)  # Poll every 60 seconds

        super().__init__(
            hass,
            _LOGGER,
            name="WatchYourLAN",
            update_interval=update_interval,
        )

        # Ensure self.config_entry is not None before accessing its data
        if self.config_entry is None:
            raise ValueError("config_entry is None, cannot access configuration data")

        # Use self.config_entry directly, as it's available from the superclass
        self.api_client = WatchYourLANClient(
            base_url=self.config_entry.data[CONF_URL], async_mode=True
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from the WatchYourLAN API with retries."""
        try:
            return await self.api_client.get_all_hosts()
        except (ConnectError, HTTPStatusError) as e:
            _LOGGER.error("Failed to fetch data from WatchYourLAN")
            raise UpdateFailed(f"Error fetching data: {e}") from e
