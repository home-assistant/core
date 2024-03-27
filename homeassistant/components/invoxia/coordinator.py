"""Data coordinator for Invoxia integration."""
from __future__ import annotations

import asyncio

from gps_tracker import AsyncClient, Tracker
from gps_tracker.client.exceptions import GpsTrackerException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_UPDATE_INTERVAL, DOMAIN, LOGGER
from .helpers import GpsTrackerData


class GpsTrackerCoordinator(DataUpdateCoordinator[GpsTrackerData]):
    """Coordinator to update GpsTracker entities."""

    def __init__(
        self, hass: HomeAssistant, client: AsyncClient, tracker: Tracker
    ) -> None:
        """Coordinator for single tracker."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=DATA_UPDATE_INTERVAL,
        )
        self._client = client
        self._tracker = tracker

    async def _async_update_data(self) -> GpsTrackerData:
        """Fetch data from API."""
        LOGGER.debug("Fetching data for Tracker %u", self._tracker.id)
        async with asyncio.timeout(10):
            try:
                data = await asyncio.gather(
                    self._client.get_locations(self._tracker, max_count=1),
                    self._client.get_tracker_status(self._tracker),
                )
            except GpsTrackerException as err:
                LOGGER.warning("Could not fetch data for Tracker %u", self._tracker.id)
                raise UpdateFailed from err

        return GpsTrackerData(
            latitude=data[0][0].lat,
            longitude=data[0][0].lng,
            accuracy=data[0][0].precision,
            battery=data[1].battery,
        )
