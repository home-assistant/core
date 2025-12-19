"""Bizkaibus Coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from bizkaibus.bizkaibusAPI import BizkaibusAPI, BizkaibusArrivalTime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_STOP_ID, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
type BizkaibusConfigEntry = ConfigEntry[BizkaibusUpdateCoordinator]


@dataclass
class ArrivalData:
    """A connection data class."""

    bus_id: str
    nearest_arrival: datetime
    next_arrival: datetime | None = None
    bus_name: str | None = None


class BizkaibusUpdateCoordinator(DataUpdateCoordinator[list[ArrivalData]]):
    """Bizkaibus Update Coordinator class."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BizkaibusAPI,
        config_entry: BizkaibusConfigEntry,
    ) -> None:
        """Initialize the data service."""
        self.api = api
        self.config_entry = config_entry
        self.friendly_name = config_entry.data[CONF_STOP_ID]

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    def __arrival_time(
        self, arrivalTime: BizkaibusArrivalTime | None
    ) -> datetime | None:
        """Get arrival time."""
        if arrivalTime is None:
            return None
        start_datetime = dt_util.parse_datetime(arrivalTime.GetUTC())
        return start_datetime.astimezone() if start_datetime else None

    async def _async_update_data(self) -> list[ArrivalData]:
        """Async update wrapper."""
        timetable = await self.api.GetTimetable()

        if timetable is None:
            return []

        if timetable.name:
            self.friendly_name = timetable.name

        arrivals = []
        for arrival in timetable.arrivals.values():
            nearest_arrival = self.__arrival_time(arrival.nearestArrival)
            nearest_arrival = (
                nearest_arrival if nearest_arrival is not None else dt_util.utcnow()
            )
            next_arrival = self.__arrival_time(arrival.nextArrival)

            arrivalData = ArrivalData(
                nearest_arrival=nearest_arrival,
                bus_id=arrival.line.id,
                next_arrival=next_arrival,
                bus_name=arrival.line.route,
            )

            arrivals.append(arrivalData)

        return arrivals
