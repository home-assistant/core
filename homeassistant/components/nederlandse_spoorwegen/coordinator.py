"""Data update coordinator for Nederlandse Spoorwegen integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo

from ns_api import RequestParametersError
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NSAPIWrapper
from .const import (
    ATTR_FIRST_TRIP,
    ATTR_NEXT_TRIP,
    ATTR_ROUTE,
    ATTR_ROUTES,
    ATTR_TRIPS,
    CONF_FROM,
    CONF_ROUTES,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
)
from .utils import (
    generate_route_key,
    get_current_utc_timestamp,
    is_station_cache_valid,
    normalize_station_code,
    validate_route_structure,
)

_LOGGER = logging.getLogger(__name__)

# Station cache validity (24 hours)
STATION_CACHE_DURATION = timedelta(days=1)


class NSDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from Nederlandse Spoorwegen API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_wrapper: NSAPIWrapper,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=3),
            config_entry=config_entry,
        )
        self.api_wrapper = api_wrapper
        self.config_entry = config_entry
        self._unavailable_logged = False

    async def test_connection(self) -> None:
        """Test connection to the API."""
        try:
            await self.api_wrapper.validate_api_key()
        except Exception as ex:
            _LOGGER.debug("Connection test failed: %s", ex)
            raise

    def _get_routes(self) -> list[dict[str, Any]]:
        """Get routes from config entry subentries or fallback to options/data."""
        if self.config_entry is None:
            return []

        # First, try to get routes from subentries (new format)
        routes = []
        for subentry in self.config_entry.subentries.values():
            if subentry.subentry_type == "route":
                # Convert subentry data to route format
                route_data = dict(subentry.data)
                # Ensure route has a route_id
                if "route_id" not in route_data:
                    route_data["route_id"] = subentry.subentry_id
                routes.append(route_data)

        # If we have routes from subentries, use those
        if routes:
            return routes

        # Fallback to legacy format (for backward compatibility during migration)
        return self.config_entry.options.get(
            CONF_ROUTES, self.config_entry.data.get(CONF_ROUTES, [])
        )

    def _is_station_cache_valid(self, stations_updated: str | None) -> bool:
        """Check if station cache is still valid."""
        return is_station_cache_valid(stations_updated)

    async def _refresh_station_cache(self) -> list[dict[str, Any]] | None:
        """Refresh station cache if needed."""
        try:
            stations = await self.api_wrapper.get_stations()
        except Exception as exc:
            if not self._unavailable_logged:
                _LOGGER.info("NS API unavailable, using cached station data: %s", exc)
                self._unavailable_logged = True
            raise
        else:
            # Safely update runtime_data if available
            if (
                self.config_entry
                and hasattr(self.config_entry, "runtime_data")
                and self.config_entry.runtime_data
            ):
                try:
                    self.config_entry.runtime_data.stations = stations
                    self.config_entry.runtime_data.stations_updated = (
                        get_current_utc_timestamp()
                    )
                except (AttributeError, TypeError) as ex:
                    _LOGGER.debug("Error updating runtime_data: %s", ex)

            return stations

    def _get_cached_stations(self) -> tuple[list[dict[str, Any]] | None, str | None]:
        """Get cached stations and update timestamp from runtime data."""
        if not (
            self.config_entry
            and hasattr(self.config_entry, "runtime_data")
            and self.config_entry.runtime_data
        ):
            return None, None

        try:
            runtime_data = self.config_entry.runtime_data
            stations = getattr(runtime_data, "stations", None)
            stations_updated = getattr(runtime_data, "stations_updated", None)
        except (AttributeError, TypeError) as ex:
            _LOGGER.debug("Error accessing runtime_data: %s", ex)
            return None, None
        else:
            return stations, stations_updated

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library with proper runtime data handling."""
        try:
            # Get routes from config entry first
            routes = self._get_routes()
            if not routes:
                _LOGGER.debug("No routes configured")
                return {ATTR_ROUTES: {}}

            # Ensure station data is available only if we have routes
            stations = await self._ensure_stations_available()
            if not stations:
                raise UpdateFailed("Failed to fetch stations and no cache available")

            # Fetch trip data for each route
            route_data = await self._fetch_route_data(routes)

            # Log recovery if previously unavailable
            if self._unavailable_logged:
                _LOGGER.info("NS API connection restored")
                self._unavailable_logged = False

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.Timeout,
        ) as err:
            _LOGGER.error("Error communicating with NS API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return {ATTR_ROUTES: route_data}

    async def _ensure_stations_available(self) -> list[dict[str, Any]] | None:
        """Ensure station data is available, fetching if cache is expired."""
        stations, stations_updated = self._get_cached_stations()

        # Check if cache is valid
        if stations and self._is_station_cache_valid(stations_updated):
            return stations

        # Cache expired or missing, refresh
        try:
            return await self._refresh_station_cache()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.Timeout,
            RequestParametersError,
        ):
            # If refresh fails and we have cached data, use it
            if stations:
                _LOGGER.warning("Using stale station cache due to API unavailability")
                return stations
            # No cached data available
            return None

    async def _fetch_route_data(self, routes: list[dict[str, Any]]) -> dict[str, Any]:
        """Fetch trip data for all routes."""
        route_data = {}

        for route in routes:
            if not isinstance(route, dict):
                _LOGGER.warning("Skipping invalid route data: %s", route)
                continue

            route_key = self._generate_route_key(route)
            if not route_key:
                continue

            try:
                trips = await self._get_trips_for_route(route)
                route_data[route_key] = {
                    ATTR_ROUTE: route,
                    ATTR_TRIPS: trips,
                    ATTR_FIRST_TRIP: trips[0] if trips else None,
                    ATTR_NEXT_TRIP: trips[1] if len(trips) > 1 else None,
                }
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
                requests.exceptions.Timeout,
            ) as err:
                _LOGGER.warning(
                    "Error fetching trips for route %s: %s",
                    route.get(CONF_NAME, route_key),
                    err,
                )
                # Add empty route data to maintain structure
                route_data[route_key] = {
                    ATTR_ROUTE: route,
                    ATTR_TRIPS: [],
                    ATTR_FIRST_TRIP: None,
                    ATTR_NEXT_TRIP: None,
                }

        return route_data

    def _generate_route_key(self, route: dict[str, Any]) -> str | None:
        """Generate a stable route key for a route."""
        # Generate stable route key
        route_id = route.get("route_id")
        if route_id and isinstance(route_id, str):
            return route_id

        # Use centralized route key generation for basic routes
        basic_key = generate_route_key(route)
        if not basic_key:
            _LOGGER.warning("Skipping route with missing stations: %s", route)
            return None

        # Build NS-specific key with name prefix
        name = route.get(CONF_NAME, "")
        route_key = f"{name}_{basic_key}"

        # Add via station if present
        via_station = route.get(CONF_VIA, "")
        if via_station:
            route_key += f"_{normalize_station_code(via_station)}"

        return route_key

    async def _get_trips_for_route(self, route: dict[str, Any]) -> list[Any]:
        """Get trips for a specific route with validation and normalization."""
        # Validate route structure
        if not self._validate_route_structure(route):
            return []

        # Normalize station codes
        normalized_route = self._normalize_route_stations(route)

        # Validate stations exist
        if not self._validate_route_stations(normalized_route):
            return []

        # Build trip time
        trip_time = self._build_trip_time(normalized_route.get(CONF_TIME, ""))

        try:
            trips = await self.api_wrapper.get_trips(
                normalized_route[CONF_FROM],
                normalized_route[CONF_TO],
                normalized_route.get(CONF_VIA) or None,
                departure_time=trip_time,
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as ex:
            _LOGGER.error("Error calling API wrapper get_trips: %s", ex)
            return []
        else:
            return trips or []

    def _validate_route_structure(self, route: dict[str, Any]) -> bool:
        """Validate route has required structure."""
        # Use centralized validation for basic structure
        if not validate_route_structure(route):
            _LOGGER.warning("Skipping malformed route: %s", route)
            return False

        # Additional NS-specific validation for required name field
        if CONF_NAME not in route:
            _LOGGER.warning("Skipping malformed route: %s", route)
            return False

        # Fill in missing optional keys with empty string
        optional_keys = {CONF_VIA, CONF_TIME}
        for key in optional_keys:
            if key not in route:
                route[key] = ""

        return True

    def _normalize_route_stations(self, route: dict[str, Any]) -> dict[str, Any]:
        """Normalize station codes in route."""
        normalized_route = route.copy()

        # Use centralized station code normalization
        normalized_route[CONF_FROM] = normalize_station_code(route.get(CONF_FROM, ""))
        normalized_route[CONF_TO] = normalize_station_code(route.get(CONF_TO, ""))

        via_station = route.get(CONF_VIA, "")
        if via_station:
            normalized_route[CONF_VIA] = normalize_station_code(via_station)

        return normalized_route

    def _validate_route_stations(self, route: dict[str, Any]) -> bool:
        """Validate route stations exist in NS station list."""
        valid_station_codes = self.get_station_codes()

        from_station = route[CONF_FROM]
        to_station = route[CONF_TO]
        via_station = route.get(CONF_VIA, "")

        if from_station not in valid_station_codes:
            _LOGGER.error(
                "From station '%s' not found in NS station list for route: %s",
                from_station,
                route,
            )
            return False

        if to_station not in valid_station_codes:
            _LOGGER.error(
                "To station '%s' not found in NS station list for route: %s",
                to_station,
                route,
            )
            return False

        if via_station and via_station not in valid_station_codes:
            _LOGGER.error(
                "Via station '%s' not found in NS station list for route: %s",
                via_station,
                route,
            )
            return False

        return True

    def _build_trip_time(self, time_value: str) -> datetime:
        """Build trip time from configured time or current time."""
        # Validate time format if provided
        if time_value and not re.match(r"^\d{2}:\d{2}(:\d{2})?$", time_value.strip()):
            _LOGGER.warning("Ignoring invalid time value '%s'", time_value)
            time_value = ""

        tz_nl = ZoneInfo("Europe/Amsterdam")
        now_nl = datetime.now(tz=tz_nl)

        if time_value:
            try:
                hour, minute, *rest = map(int, time_value.split(":"))
                return now_nl.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except ValueError:
                _LOGGER.warning(
                    "Failed to parse time value '%s', using current time", time_value
                )

        return now_nl

    def get_station_codes(self) -> set[str]:
        """Get valid station codes from runtime data."""
        if (
            self.config_entry is not None
            and hasattr(self.config_entry, "runtime_data")
            and self.config_entry.runtime_data
            and self.config_entry.runtime_data.stations
        ):
            return self.api_wrapper.get_station_codes(
                self.config_entry.runtime_data.stations
            )
        return set()
