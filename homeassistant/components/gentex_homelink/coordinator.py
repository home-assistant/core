"""Makes requests to the state server and stores the resulting data so that the buttons can access it."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import POLLING_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HomelinkCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass: HomeAssistant, provider, config_entry) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Homelink Coordinator",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=POLLING_INTERVAL),
        )
        self.provider = provider
        self.last_sync_timestamp = None
        self.last_sync_id = None
        self.config_entry = config_entry

    async def _async_setup(self):
        """Set up the coordinator.

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with asyncio.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.
            # listening_idx = set(self.async_contexts())
            should_sync, devices = await self.provider.get_state()

            if (
                should_sync
                and should_sync["requestId"] != self.last_sync_id
                and self.config_entry.data["last_update_id"] != should_sync["requestId"]
                and should_sync["timestamp"] != self.last_sync_timestamp
            ):
                config_data = self.config_entry.data.copy()
                config_data["last_update_id"] = should_sync["requestId"]

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=config_data
                )
                self.last_sync_id = should_sync["requestId"]
                self.last_sync_timestamp = should_sync["timestamp"]
            return devices
