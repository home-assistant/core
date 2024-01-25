from datetime import timedelta
import logging
from typing import TypedDict

import aiohttp
import async_timeout

from homeassistant import core
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class Event(TypedDict):
    eventId: str


class SwitchgridCoordinator(DataUpdateCoordinator[list[Event]]):
    """Coordinator for updating data from the Switchgrid API."""

    def __init__(self, hass: core.HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Switchgrid Events Data",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=10),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                # Grab active context variables to limit data required to be fetched from API
                # Note: using context is not required if there is no need or ability to limit
                # data retrieved from API.
                # listening_idx = set(self.async_contexts())
                # return await self.my_api.fetch_data(listening_idx)
                # GET request to https://app.switchgrid.tech/api/homeassistant/events
                params = {}
                headers = {}
                url = "https://app.switchgrid.tech/api/homeassistant/events"
                # url = "https://licarth.eu.ngrok.io/api/homeassistant/events"
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, params=params, headers=headers
                    ) as response:
                        response.raise_for_status()
                        response_object = await response.json()
                        return response_object

        except aiohttp.ClientError as error:
            raise UpdateFailed(error) from error

    def next_event(self):
        return self.data
