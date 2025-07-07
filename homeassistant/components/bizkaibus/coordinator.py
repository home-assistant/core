"""Bizkaibus Coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from bizkaibus.bizkaibus import BizkaibusArrival, BizkaibusData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
type BizkaibusConfigEntry = ConfigEntry[BizkaibusUpdateCoordinator]


@dataclass
class DataConnection:
    """A connection data class."""

    departure: datetime | None
    train_number: str


class BizkaibusUpdateCoordinator(DataUpdateCoordinator[list[DataConnection]]):
    """Bizkaibus Update Coordinator class."""

    def __init__(self, hass: HomeAssistant, api: BizkaibusData) -> None:
        """Initialize the data service."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    def __departure_time(self, arrival: BizkaibusArrival) -> datetime | None:
        """Get departure time."""
        start_datetime = dt_util.parse_datetime(arrival.closestArrival.GetAbsolute())
        return start_datetime.astimezone() if start_datetime else None

    async def _async_update_data(self) -> list[DataConnection]:
        """Async update wrapper."""
        timetable = await self.api.GetTimetable()

        if timetable is None:
            return []

        result = []
        for arrival in timetable.arrivals.values():
            departure = self.__departure_time(arrival)
            dataConnection = DataConnection(
                departure=departure,
                train_number=arrival.line.route,
            )
            result.append(dataConnection)

        return result
