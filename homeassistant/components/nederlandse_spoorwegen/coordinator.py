"""DataUpdateCoordinator for Nederlandse Spoorwegen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from ns_api import NSAPI, Trip
from requests.exceptions import ConnectionError, HTTPError, Timeout

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    AMS_TZ,
    CONF_FROM,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _current_time_nl(tomorrow: bool = False) -> datetime:
    """Return current time for today or tomorrow in Europe/Amsterdam timezone."""
    now = dt_util.now(AMS_TZ)
    if tomorrow:
        now = now + timedelta(days=1)
    return now


def _format_time(dt: datetime) -> str:
    """Format datetime to NS API format (DD-MM-YYYY HH:MM)."""
    return dt.strftime("%d-%m-%Y %H:%M")


type NSConfigEntry = ConfigEntry[dict[str, NSDataUpdateCoordinator]]


@dataclass
class NSRouteResult:
    """Data class for Nederlandse Spoorwegen API results."""

    trips: list[Trip]
    first_trip: Trip | None = None
    next_trip: Trip | None = None


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
        self.name = subentry.data[CONF_NAME]
        self.departure = subentry.data[CONF_FROM]
        self.destination = subentry.data[CONF_TO]
        self.via = subentry.data.get(CONF_VIA)
        self.departure_time = subentry.data.get(CONF_TIME)  # str | None

    async def _async_update_data(self) -> NSRouteResult:
        """Fetch data from NS API for this specific route."""
        trips: list[Trip] = []
        first_trip: Trip | None = None
        next_trip: Trip | None = None
        try:
            trips = await self._get_trips(
                self.departure,
                self.destination,
                self.via,
                departure_time=self.departure_time,
            )

        except (ConnectionError, Timeout, HTTPError, ValueError) as err:
            # Surface API failures to Home Assistant so the entities become unavailable
            raise UpdateFailed(f"API communication error: {err}") from err

        # Filter out trips that have already departed (trips are already sorted)
        future_trips = self._remove_trips_in_the_past(trips)

        # If a specific time is configured, filter to only show trips at or after that time
        if self.departure_time:
            reference_time = self._get_time_from_route(self.departure_time)
            future_trips = self._filter_trips_at_or_after_time(
                future_trips, reference_time
            )

        # Process trips to find current and next departure
        first_trip, next_trip = self._get_first_and_next_trips(future_trips)

        return NSRouteResult(
            trips=trips,
            first_trip=first_trip,
            next_trip=next_trip,
        )

    def _get_time_from_route(self, time_str: str | None) -> datetime:
        """Convert time string to datetime with automatic rollover to tomorrow if needed."""
        if not time_str:
            return _current_time_nl()

        if (
            isinstance(time_str, str)
            and len(time_str.split(":")) in (2, 3)
            and " " not in time_str
        ):
            # Parse time-only string (HH:MM or HH:MM:SS)
            time_only = time_str[:5]  # Take HH:MM only
            hours, minutes = map(int, time_only.split(":"))

            # Create datetime with today's date and the specified time
            now = _current_time_nl()
            result_dt = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

            # If the time is more than 1 hour in the past, assume user meant tomorrow
            if (now - result_dt).total_seconds() > 3600:
                result_dt = _current_time_nl(tomorrow=True).replace(
                    hour=hours, minute=minutes, second=0, microsecond=0
                )

            return result_dt

        # Fallback: use current date and time
        return _current_time_nl()

    async def _get_trips(
        self,
        departure: str,
        destination: str,
        via: str | None = None,
        departure_time: str | None = None,
    ) -> list[Trip]:
        """Get trips from NS API, sorted by departure time."""

        # Convert time to datetime with rollover logic, then format for API
        reference_time = self._get_time_from_route(departure_time)
        time_str = _format_time(reference_time)

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

        return self._sort_trips_by_departure(trips)

    def _sort_trips_by_departure(self, trips: list[Trip]) -> list[Trip]:
        """Sort trips by departure time (actual or planned)."""
        return sorted(
            trips,
            key=lambda trip: (
                trip.departure_time_actual
                if trip.departure_time_actual is not None
                else trip.departure_time_planned
                if trip.departure_time_planned is not None
                else _current_time_nl()
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
        now = _current_time_nl()
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

    def _filter_trips_at_or_after_time(
        self, trips: list[Trip], reference_time: datetime
    ) -> list[Trip]:
        """Filter trips to only those at or after the reference time (ignoring date).

        The API returns trips spanning multiple days, so we simply filter
        by time component to show only trips at or after the configured time.
        """
        filtered_trips = []
        ref_time_only = reference_time.time()

        for trip in trips:
            departure_time = (
                trip.departure_time_actual
                if trip.departure_time_actual is not None
                else trip.departure_time_planned
            )

            if departure_time is None:
                continue

            # Make naive datetimes timezone-aware if needed
            if (
                departure_time.tzinfo is None
                or departure_time.tzinfo.utcoffset(departure_time) is None
            ):
                departure_time = departure_time.replace(tzinfo=reference_time.tzinfo)

            # Compare only the time component, ignoring the date
            trip_time_only = departure_time.time()
            if trip_time_only >= ref_time_only:
                filtered_trips.append(trip)

        return filtered_trips

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
