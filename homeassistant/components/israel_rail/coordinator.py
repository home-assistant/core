"""DataUpdateCoordinator for the israel rail integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from israelrailapi import TrainSchedule
from israelrailapi.api import TrainRoute
from israelrailapi.train_station import station_name_to_id

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DEFAULT_SCAN_INTERVAL, DEPARTURES_COUNT, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class DataConnection:
    """A connection data class."""

    departure: datetime | None
    duration: int | None
    platform: str
    remaining_time: str
    start: str
    destination: str
    train_number: str
    transfers: int


def calculate_duration_in_seconds(start_time: str, end_time: str) -> int | None:
    """Transform and calculate the duration from start and end time into seconds."""
    end_time_date = dt_util.parse_datetime(end_time)
    start_time_date = dt_util.parse_datetime(start_time)
    if not end_time_date or not start_time_date:
        return None
    return (end_time_date - start_time_date).seconds


def departure_time(train_route: TrainRoute) -> datetime | None:
    """Get departure time."""
    start_datetime = dt_util.parse_datetime(train_route.start_time)
    return start_datetime.astimezone() if start_datetime else None


def remaining_time(departure) -> timedelta | None:
    """Calculate the remaining time for the departure."""
    departure_datetime = dt_util.parse_datetime(departure)

    if departure_datetime:
        return dt_util.as_local(departure_datetime) - dt_util.as_local(dt_util.utcnow())
    return None


class IsraelRailDataUpdateCoordinator(DataUpdateCoordinator[list[DataConnection]]):
    """A IsraelRail Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        train_schedule: TrainSchedule,
        start: str,
        destination: str,
    ) -> None:
        """Initialize the IsraelRail data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._train_schedule = train_schedule
        self._start = start
        self._destination = destination

    async def _async_update_data(self) -> list[DataConnection]:
        try:
            train_routes = await self.hass.async_add_executor_job(
                self._train_schedule.query,
                self._start,
                self._destination,
                datetime.now().strftime("%Y-%m-%d"),
                datetime.now().strftime("%H:%M"),
            )
        except Exception as e:
            raise UpdateFailed(
                "Unable to connect and retrieve data from israelrail api",
            ) from e

        return [
            DataConnection(
                departure=departure_time(train_routes[i]),
                train_number=train_routes[i].trains[0].data["trainNumber"],
                platform=train_routes[i].trains[0].platform,
                transfers=len(train_routes[i].trains) - 1,
                duration=calculate_duration_in_seconds(
                    train_routes[i].start_time, train_routes[i].end_time
                ),
                start=station_name_to_id(train_routes[i].trains[0].src),
                destination=station_name_to_id(train_routes[i].trains[-1].dst),
                remaining_time=str(remaining_time(train_routes[i].trains[0].departure)),
            )
            for i in range(DEPARTURES_COUNT)
            if len(train_routes) > i and train_routes[i] is not None
        ]
