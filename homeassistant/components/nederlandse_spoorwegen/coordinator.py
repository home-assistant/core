"""DataUpdateCoordinator for Nederlandse Spoorwegen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging

from ns_api import NSAPI, Station, Trip
from requests.exceptions import ConnectionError, HTTPError, Timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import AMS_TZ, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _now_nl() -> datetime:
    """Return current time in Europe/Amsterdam timezone."""
    return dt_util.now(AMS_TZ)


@dataclass
class NSRouteData:
    """Data class for Nederlandse Spoorwegen route information."""

    departure: str
    destination: str
    via: str | None = None
    time: str | None = None
    trips: list[Trip] = field(default_factory=list)
    first_trip: Trip | None = None
    next_trip: Trip | None = None
    error: str | None = None


class NSDataUpdateCoordinator(DataUpdateCoordinator[NSRouteData]):
    """Class to manage fetching Nederlandse Spoorwegen data from the API for a single route."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        route_id: str,
        route_data: dict[str, str],
    ) -> None:
        """Initialize the coordinator for a specific route."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{route_id}",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.config_entry = config_entry
        self.route_id = route_id
        self.nsapi = NSAPI(config_entry.data[CONF_API_KEY])
        self.route_config = NSRouteData(
            departure=route_data.get("from", ""),
            destination=route_data.get("to", ""),
            via=route_data.get("via"),
            time=route_data.get("time"),
        )
        self.stations: list[Station] = []

    async def _async_update_data(self) -> NSRouteData:
        """Fetch data from NS API for this specific route."""
        try:
            route_data = await self._get_trips_for_route(self.route_config)
        except (
            ConnectionError,
            Timeout,
            HTTPError,
            ValueError,
        ) as err:
            _LOGGER.error("Error fetching data for route %s: %s", self.route_id, err)
            return NSRouteData(
                departure=self.route_config.departure,
                destination=self.route_config.destination,
                via=self.route_config.via,
                time=self.route_config.time,
                error=str(err),
            )
        if route_data.error:
            _LOGGER.error(
                "Error fetching data for route %s: %s", self.route_id, route_data.error
            )
            return NSRouteData(
                departure=self.route_config.departure,
                destination=self.route_config.destination,
                via=self.route_config.via,
                time=self.route_config.time,
                error=route_data.error,
            )
        return route_data

    async def _get_trips_for_route(self, route_config: NSRouteData) -> NSRouteData:
        """Get_get_trips_for_route route."""
        trips: list[Trip] = []
        first_trip: Trip | None = None
        next_trip: Trip | None = None
        error: str | None = None
        try:
            trips = await self._get_trips(
                route_config.departure,
                route_config.destination,
                route_config.via,
                route_config.time,
            )

            # Filter out trips that have already departed (trips are already sorted)
            future_trips = self._remove_trips_in_the_past(trips)

            # Process trips to find current and next departure
            first_trip, next_trip = self._get_first_and_next_trips(future_trips)

        except (ConnectionError, Timeout, HTTPError, ValueError) as err:
            error = f"Error communicating with NS API: {err}"
            _LOGGER.error(error)

        return NSRouteData(
            departure=route_config.departure,
            destination=route_config.destination,
            via=route_config.via,
            time=route_config.time,
            trips=trips if not error else [],
            first_trip=first_trip if not error else None,
            next_trip=next_trip if not error else None,
            error=error,
        )

    def _get_time_from_route(self, time_str: str | None) -> str:
        """Combine today's date with a time string if needed."""
        if not time_str:
            return _now_nl().strftime("%d-%m-%Y %H:%M")

        try:
            # First, try to parse as a full date-time string and extract only the time
            parsed_datetime = datetime.strptime(time_str, "%d-%m-%Y %H:%M")
        except ValueError:
            try:
                # If that fails, check if it's a time-only string (HH:MM or HH:MM:SS)
                if len(time_str.split(":")) in (2, 3) and " " not in time_str:
                    today = _now_nl().strftime("%d-%m-%Y")
                    return f"{today} {time_str[:5]}"
            except (ValueError, IndexError):
                pass
            # Fallback: use current date and time
            return _now_nl().strftime("%d-%m-%Y %H:%M")
        else:
            # Extract time and combine with today's date
            time_only = parsed_datetime.strftime("%H:%M")
            today = _now_nl().strftime("%d-%m-%Y")
            return f"{today} {time_only}"

    async def _get_trips(
        self,
        departure: str,
        destination: str,
        via: str | None = None,
        time: str | None = None,
    ) -> list[Trip]:
        """Get trips from NS API, sorted by departure time."""

        # Convert time to full date-time string if needed and default to Dutch local time if not provided
        time_str = self._get_time_from_route(time)

        try:
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

        except (
            ConnectionError,
            Timeout,
            HTTPError,
            ValueError,
        ) as err:
            _LOGGER.error("Error communicating with NS API: %s", err)
            return []

    async def get_stations(self) -> list[Station]:
        """Get all stations from NS API."""
        try:
            stations = await self.hass.async_add_executor_job(self.nsapi.get_stations)
        except (HTTPError, ValueError, ConnectionError, Timeout) as err:
            _LOGGER.warning("Failed to fetch stations: %s", err)
            return []
        else:
            return stations or []

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
