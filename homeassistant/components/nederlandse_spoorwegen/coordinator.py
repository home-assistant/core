"""Data update coordinator for Nederlandse Spoorwegen integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from json import JSONDecodeError
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo

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

_LOGGER = logging.getLogger(__name__)


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
            update_interval=timedelta(minutes=1),
            config_entry=config_entry,
        )
        self.api_wrapper = api_wrapper
        self.config_entry = config_entry

    async def test_connection(self) -> None:
        """Test connection to the API."""
        try:
            await self.api_wrapper.validate_api_key()
        except Exception as ex:
            _LOGGER.debug("Connection test failed: %s", ex)
            raise

    def _get_routes(self) -> list[dict[str, Any]]:
        """Get routes from config entry subentries (preferred) or fallback to options/data."""
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

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Use runtime_data to cache stations and timestamp
            runtime_data = getattr(self.config_entry, "runtime_data", None)
            stations = runtime_data.stations if runtime_data else None
            stations_updated = runtime_data.stations_updated if runtime_data else None
            station_cache_expired = False
            now_utc = datetime.now(UTC)
            if not stations or not stations_updated:
                station_cache_expired = True
            else:
                try:
                    updated_dt = datetime.fromisoformat(stations_updated)
                    if (now_utc - updated_dt) > timedelta(days=1):
                        station_cache_expired = True
                except (ValueError, TypeError):
                    station_cache_expired = True

            if station_cache_expired:
                try:
                    stations = await self.api_wrapper.get_stations()
                    # Store full stations in runtime_data for UI dropdowns
                    if self.config_entry is not None:
                        runtime_data = self.config_entry.runtime_data
                        runtime_data.stations = stations
                        runtime_data.stations_updated = now_utc.isoformat()
                except (TypeError, JSONDecodeError) as exc:
                    # Handle specific JSON parsing errors (None passed to json.loads)
                    _LOGGER.warning(
                        "Failed to parse stations response from NS API, using cached data: %s",
                        exc,
                    )
                    # Keep using existing stations data if available
                    if not stations:
                        raise UpdateFailed(
                            f"Failed to parse stations response: {exc}"
                        ) from exc

            # Get routes from config entry options or data
            routes = self._get_routes()

            # Fetch trip data for each route
            route_data = {}
            for route in routes:
                # Use route_id as the stable key if present
                route_id = route.get("route_id")
                if route_id:
                    route_key = route_id
                else:
                    route_key = f"{route.get(CONF_NAME, '')}_{route.get(CONF_FROM, '')}_{route.get(CONF_TO, '')}"
                    if route.get(CONF_VIA):
                        route_key += f"_{route.get(CONF_VIA)}"

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
                ) as err:
                    _LOGGER.warning(
                        "Error fetching trips for route %s: %s",
                        route.get(CONF_NAME, ""),
                        err,
                    )
                    route_data[route_key] = {
                        ATTR_ROUTE: route,
                        ATTR_TRIPS: [],
                        ATTR_FIRST_TRIP: None,
                        ATTR_NEXT_TRIP: None,
                    }

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Invalid request parameters: {err}") from err
        else:
            return {
                ATTR_ROUTES: route_data,
            }

    async def _get_trips_for_route(self, route: dict[str, Any]) -> list[Any]:
        """Get trips for a specific route, validating time field and structure."""
        # Ensure all required and optional keys are present
        required_keys = {CONF_NAME, CONF_FROM, CONF_TO}
        optional_keys = {CONF_VIA, CONF_TIME}
        if not isinstance(route, dict) or not required_keys.issubset(route):
            _LOGGER.warning("Skipping malformed route: %s", route)
            return []
        # Fill in missing optional keys with empty string
        for key in optional_keys:
            if key not in route:
                route[key] = ""
        # Validate 'time' is a string in the expected time format (HH:MM or HH:MM:SS) or empty
        time_value = route.get(CONF_TIME, "")
        if time_value:
            if not (
                isinstance(time_value, str)
                and re.match(r"^\d{2}:\d{2}(:\d{2})?$", time_value.strip())
            ):
                _LOGGER.warning(
                    "Ignoring invalid time value '%s' for route %s", time_value, route
                )
                time_value = ""
        # Normalize station codes to uppercase for comparison and storage
        from_station = route.get(CONF_FROM, "").upper()
        to_station = route.get(CONF_TO, "").upper()
        via_station = route.get(CONF_VIA, "").upper() if route.get(CONF_VIA) else ""
        # Overwrite the route dict with uppercase codes
        route[CONF_FROM] = from_station
        route[CONF_TO] = to_station
        if CONF_VIA in route:
            route[CONF_VIA] = via_station
        # Use the stored station codes from runtime_data for validation
        valid_station_codes = self.get_station_codes()
        # Store approved station codes in runtime_data for use in config flow
        current_codes = list(self.get_station_codes())
        # Always sort both lists before comparing and storing
        sorted_valid_codes = sorted(valid_station_codes)
        sorted_current_codes = sorted(current_codes)
        if sorted_valid_codes != sorted_current_codes:
            if (
                self.config_entry is not None
                and hasattr(self.config_entry, "runtime_data")
                and self.config_entry.runtime_data
            ):
                self.config_entry.runtime_data.approved_station_codes = (
                    sorted_valid_codes
                )
        if from_station not in valid_station_codes:
            _LOGGER.error(
                "'from' station code '%s' not found in NS station list for route: %s",
                from_station,
                route,
            )
            return []
        if to_station not in valid_station_codes:
            _LOGGER.error(
                "'to' station code '%s' not found in NS station list for route: %s",
                to_station,
                route,
            )
            return []
        # Build trip time string for NS API (use configured time or now)
        tz_nl = ZoneInfo("Europe/Amsterdam")
        now_nl = datetime.now(tz=tz_nl)
        if time_value:
            try:
                hour, minute, *rest = map(int, time_value.split(":"))
                trip_time = now_nl.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
            except ValueError:
                trip_time = now_nl
        else:
            trip_time = now_nl
        try:
            # Use the API wrapper which has a different signature
            trips = await self.api_wrapper.get_trips(
                from_station,
                to_station,
                via_station if via_station else None,
                departure_time=trip_time,
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as ex:
            _LOGGER.error("Error calling API wrapper get_trips: %s", ex)
            return []

        # Trips are already filtered for future departures in the API wrapper
        return trips or []

    def _build_station_mapping(self, stations: list) -> dict[str, str]:
        """Build a mapping of station codes to names from fetched station data."""
        station_mapping = {}

        for station in stations:
            code = None
            name = None

            if hasattr(station, "code") and hasattr(station, "name"):
                # Standard format: separate code and name attributes
                code = station.code
                name = station.name
            elif isinstance(station, dict):
                # Dict format
                code = station.get("code")
                name = station.get("name")
            else:
                # Handle string format or object with __str__ method
                station_str = str(station)

                # Remove class name wrapper if present (e.g., "<Station> AC Abcoude" -> "AC Abcoude")
                if station_str.startswith("<") and "> " in station_str:
                    station_str = station_str.split("> ", 1)[1]

                # Try to parse "CODE Name" format
                parts = station_str.strip().split(" ", 1)
                if (
                    len(parts) == 2 and len(parts[0]) <= 4 and parts[0].isupper()
                ):  # Station codes are typically 2-4 uppercase chars
                    code, name = parts
                else:
                    # If we can't parse it properly, skip this station silently
                    continue

            # Only add if we have both code and name
            if code and name:
                station_mapping[code.upper()] = name.strip()

        return station_mapping

    def get_station_codes(self) -> set[str]:
        """Get valid station codes from runtime data."""
        if (
            self.config_entry is not None
            and hasattr(self.config_entry, "runtime_data")
            and self.config_entry.runtime_data
            and self.config_entry.runtime_data.stations
        ):
            station_mapping = self._build_station_mapping(
                self.config_entry.runtime_data.stations
            )
            return set(station_mapping.keys())
        return set()
