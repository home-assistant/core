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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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


class NSDataUpdateCoordinator(DataUpdateCoordinator[dict[str, NSRouteData]]):
    """Class to manage fetching Nederlandse Spoorwegen data from the API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.config_entry = config_entry
        self.nsapi = NSAPI(config_entry.data[CONF_API_KEY])
        self._route_configs: dict[str, NSRouteData] = {}
        self.stations: list[Station] = []

    def add_route(self, route_id: str, route_data: NSRouteData) -> None:
        """Add a route for data fetching."""
        self._route_configs[route_id] = route_data

    def remove_route(self, route_id: str) -> None:
        """Remove a route."""
        self._route_configs.pop(route_id, None)

    async def _async_update_data(self) -> dict[str, NSRouteData]:
        """Fetch data from NS API."""
        if not self._route_configs:
            return {}

        updated_data = {}

        for route_id, route_config in self._route_configs.items():
            try:
                route_data = await self._get_trips_for_route(route_config)
                updated_data[route_id] = route_data
            except (
                ConnectionError,
                Timeout,
                HTTPError,
                ValueError,
                UpdateFailed,
            ) as err:
                _LOGGER.error("Error fetching data for route %s: %s", route_id, err)
                # Keep existing data if available, otherwise create error state
                if self.data and route_id in self.data:
                    updated_data[route_id] = self.data[route_id]
                else:
                    updated_data[route_id] = NSRouteData(
                        departure=route_config.departure,
                        destination=route_config.destination,
                        via=route_config.via,
                        time=route_config.time,
                        error=str(err),
                    )

        return updated_data

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

    async def _get_trips(
        self,
        departure: str,
        destination: str,
        via: str | None = None,
        time: str | None = None,
    ) -> list[Trip]:
        """Get trips from NS API, sorted by departure time."""

        # ns_api expects Dutch local time strings; default to current NL time
        time_str = time if time else _now_nl().strftime("%d-%m-%Y %H:%M")

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

    def _find_next_trip(self, future_trips, first_trip) -> Trip | None:
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

    def get_route_data(self, route_id: str) -> NSRouteData | None:
        """Get data for a specific route."""
        return self.data.get(route_id) if self.data else None
