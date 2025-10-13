"""DataUpdateCoordinator for Nederlandse Spoorwegen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
import logging

from ns_api import NSAPI, Trip
from requests.exceptions import ConnectionError, HTTPError, Timeout

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import AMS_TZ, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _now_nl() -> datetime:
    """Return current time in Europe/Amsterdam timezone."""
    return dt_util.now(AMS_TZ)


type NSConfigEntry = ConfigEntry[dict[str, NSDataUpdateCoordinator]]


@dataclass
class NSRouteResult:
    """Data class for Nederlandse Spoorwegen API results."""

    trips: list[Trip]
    first_trip: Trip | None = None
    next_trip: Trip | None = None
    error: str | None = None


class NSDataUpdateCoordinator(DataUpdateCoordinator[NSRouteResult]):
    """Class to manage fetching Nederlandse Spoorwegen data from the API for a single route."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NSConfigEntry,
        route_id: str,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the coordinator for a specific route."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{route_id}",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.id = route_id
        self.nsapi = NSAPI(config_entry.data[CONF_API_KEY])
        self.name = subentry.data["name"]
        self.departure = subentry.data["from"]
        self.destination = subentry.data["to"]
        self.via = subentry.data.get("via")
        self.departure_time = subentry.data.get("time")  # str | time | None

    async def _async_update_data(self) -> NSRouteResult:
        """Fetch data from NS API for this specific route."""
        try:
            return await self._get_trips_for_route()
        except (ConnectionError, Timeout, HTTPError, ValueError) as err:
            # Surface API failures to Home Assistant so the entities become unavailable
            raise UpdateFailed(f"API communication error: {err}") from err

    async def _get_trips_for_route(self) -> NSRouteResult:
        """Get trips for route using coordinator properties."""
        trips: list[Trip] = []
        first_trip: Trip | None = None
        next_trip: Trip | None = None
        trips = await self._get_trips(
            self.departure,
            self.destination,
            self.via,
            departure_time=self.departure_time,
        )

        # Filter out trips that have already departed (trips are already sorted)
        future_trips = self._remove_trips_in_the_past(trips)

        # Process trips to find current and next departure
        first_trip, next_trip = self._get_first_and_next_trips(future_trips)

        return NSRouteResult(
            trips=trips,
            first_trip=first_trip,
            next_trip=next_trip,
            error=None,
        )

    def _get_time_from_route(self, time_str: str | time | None) -> str:
        """Combine today's date with a time string if needed."""
        if not time_str:
            return _now_nl().strftime("%d-%m-%Y %H:%M")
        try:
            if isinstance(time_str, time):
                return _now_nl().strftime("%d-%m-%Y ") + time_str.strftime("%H:%M")
            if isinstance(time_str, str):
                if len(time_str.split(":")) in (2, 3) and " " not in time_str:
                    today = _now_nl().strftime("%d-%m-%Y")
                    return f"{today} {time_str[:5]}"
        except (ValueError, IndexError):
            pass
        # Fallback: use current date and time
        return _now_nl().strftime("%d-%m-%Y %H:%M")

    async def _get_trips(
        self,
        departure: str,
        destination: str,
        via: str | None = None,
        departure_time: str | time | None = None,
    ) -> list[Trip]:
        """Get trips from NS API, sorted by departure time."""

        # Convert time to full date-time string if needed and default to Dutch local time if not provided
        time_str = self._get_time_from_route(departure_time)

        trips = await self.hass.async_add_executor_job(
            self.nsapi.get_trips,
            time_str,  # trip_time
            departure,  # departure
            via,  # via
            destination,  # destination
            True,  # exclude_high_speed
            0,  # year_card
            2,  # max_number_of_transfers
        )

        if not trips:
            return []

        return sorted(
            trips,
            key=lambda trip: (
                trip.departure_time_actual
                if trip.departure_time_actual is not None
                else trip.departure_time_planned
                if trip.departure_time_planned is not None
                else _now_nl()
            ),
        )

    def _get_first_and_next_trips(
        self, trips: list[Trip]
    ) -> tuple[Trip | None, Trip | None]:
        """Process trips to find the first and next departure."""
        if not trips:
            return None, None

        # First trip is the earliest future trip
        first_trip = trips[0]

        # Find next trip with different departure time
        next_trip = self._find_next_trip(trips, first_trip)

        return first_trip, next_trip

    def _remove_trips_in_the_past(self, trips: list[Trip]) -> list[Trip]:
        """Filter out trips that have already departed."""
        # Compare against Dutch local time to align with ns_api timezone handling
        now = _now_nl()
        future_trips = []
        for trip in trips:
            departure_time = (
                trip.departure_time_actual
                if trip.departure_time_actual is not None
                else trip.departure_time_planned
            )
            if departure_time is not None and (
                departure_time.tzinfo is None
                or departure_time.tzinfo.utcoffset(departure_time) is None
            ):
                # Make naive datetimes timezone-aware using current reference tz
                departure_time = departure_time.replace(tzinfo=now.tzinfo)

            if departure_time and departure_time > now:
                future_trips.append(trip)
        return future_trips

    def _find_next_trip(
        self, future_trips: list[Trip], first_trip: Trip
    ) -> Trip | None:
        """Find the next trip with a different departure time than the first trip."""
        next_trip = None
        if len(future_trips) > 1:
            first_time = (
                first_trip.departure_time_actual
                if first_trip.departure_time_actual is not None
                else first_trip.departure_time_planned
            )
            for trip in future_trips[1:]:
                trip_time = (
                    trip.departure_time_actual
                    if trip.departure_time_actual is not None
                    else trip.departure_time_planned
                )
                if trip_time and first_time and trip_time > first_time:
                    next_trip = trip
                    break
        return next_trip
