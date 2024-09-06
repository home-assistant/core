"""Coordinator for the WatchYourLAN integration."""

from datetime import timedelta
import logging
from types import MappingProxyType

from watchyourlanclient import WatchYourLANClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class WatchYourLANUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the WatchYourLAN API."""

    def __init__(self, hass: HomeAssistant, config: MappingProxyType) -> None:
        """Initialize the coordinator."""
        # Set up a regular polling interval (e.g., every 60 seconds)
        update_interval = timedelta(seconds=60)  # Poll every 60 seconds

        super().__init__(
            hass,
            _LOGGER,
            name="WatchYourLAN",
            update_interval=update_interval,  # Add polling interval here
        )
        self.api_url = config.get("url")
        self.api_client = WatchYourLANClient(
            base_url=config.get("url"), async_mode=True
        )

    async def _async_update_data(self):
        """Fetch data from the WatchYourLAN API with retries."""
        try:
            return await self.api_client.get_all_hosts()
        except Exception as e:
            _LOGGER.error("Failed to fetch data from WatchYourLAN")
            raise UpdateFailed(f"Error fetching data: {e}") from e
