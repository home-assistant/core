"""Coordinator for collecting Switchgrid data."""

from asyncio import timeout
import logging

import aiohttp
from switchgrid_python_client import Event, SwitchgridClient, SwitchgridEventsResponse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SwitchgridCoordinator(DataUpdateCoordinator[SwitchgridEventsResponse]):
    """Coordinator for updating data from the Switchgrid API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SwitchgridClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Switchgrid Events Coordinator",
            update_interval=UPDATE_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> SwitchgridEventsResponse:
        try:
            async with timeout(10):
                await self._client.update()
                return self._client.data
        except aiohttp.ClientError as error:
            raise UpdateFailed(error) from error

    def next_event(self) -> Event | None:
        """Return the next (first) upcoming event."""
        now = dt_util.now()
        if self._client.data is None:
            return None
        return next(
            (event for event in self._client.data.events if event.startUtc > now), None
        )
