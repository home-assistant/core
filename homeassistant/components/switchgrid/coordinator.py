"""Coordinator for collecting Switchgrid data."""

from asyncio import timeout
import logging

import aiohttp
from switchgrid_python_client import Event, SwitchgridData, SwitchgridEventsResponse

from homeassistant import core
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SwitchgridCoordinator(DataUpdateCoordinator[SwitchgridData]):
    """Coordinator for updating data from the Switchgrid API."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        data: SwitchgridData,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Switchgrid Events Coordinator",
            update_interval=UPDATE_INTERVAL,
        )
        self._data = data

    async def _async_update_data(self) -> SwitchgridEventsResponse:
        try:
            async with timeout(10):
                await self._data.update()
                return self._data.data
        except aiohttp.ClientError as error:
            raise UpdateFailed(error) from error

    def next_event(self) -> Event | None:
        """Return the next (first) upcoming event."""
        now = dt_util.now()
        if self._data.data is None:
            return None
        return next(
            (event for event in self._data.data.events if event.startUtc > now), None
        )
