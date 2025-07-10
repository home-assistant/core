"""Data update coordinator for Nederlandse Spoorwegen integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib
import logging
import re
from typing import Any
import uuid
from zoneinfo import ZoneInfo

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_FIRST_TRIP,
    ATTR_NEXT_TRIP,
    ATTR_ROUTE,
    ATTR_ROUTES,
    ATTR_STATIONS,
    ATTR_TRIPS,
    CONF_FROM,
    CONF_ROUTES,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
)

# Import ns_api only once at runtime to avoid issues with async setup
NSAPI = importlib.import_module("ns_api").NSAPI
RequestParametersError = importlib.import_module("ns_api").RequestParametersError

_LOGGER = logging.getLogger(__name__)


class NSDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from Nederlandse Spoorwegen API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NSAPI,  # type: ignore[valid-type]
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
        self.client = client
        self.config_entry = config_entry
        self._stations: list[Any] = []

        # Assign UUID to any route missing 'route_id' (for upgrades)
        routes = self.config_entry.options.get(
            CONF_ROUTES, self.config_entry.data.get(CONF_ROUTES, [])
        )
        changed = False
        for route in routes:
            if "route_id" not in route:
                route["route_id"] = str(uuid.uuid4())
                changed = True
        if changed:
            # Save updated routes with UUIDs back to config entry
            self.hass.config_entries.async_update_entry(
                self.config_entry, options={CONF_ROUTES: routes}
            )

    async def test_connection(self) -> None:
        """Test connection to the API."""
        try:
            await self.hass.async_add_executor_job(self.client.get_stations)  # type: ignore[attr-defined]
        except Exception as ex:
            _LOGGER.debug("Connection test failed: %s", ex)
            raise

    def _get_routes(self) -> list[dict[str, Any]]:
        """Get routes from config entry options or data."""
        return (
            self.config_entry.options.get(
                CONF_ROUTES, self.config_entry.data.get(CONF_ROUTES, [])
            )
            if self.config_entry is not None
            else []
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Use runtime_data to cache station codes and timestamp
            runtime_data = (
                getattr(self.config_entry, "runtime_data", {})
                if self.config_entry is not None
                else {}
            )
            approved_station_codes = runtime_data.get("approved_station_codes")
            approved_station_codes_updated = runtime_data.get(
                "approved_station_codes_updated"
            )
            station_cache_expired = False
            now_utc = datetime.now(UTC)
            if not approved_station_codes or not approved_station_codes_updated:
                station_cache_expired = True
            else:
                try:
                    updated_dt = datetime.fromisoformat(approved_station_codes_updated)
                    if (now_utc - updated_dt) > timedelta(days=1):
                        station_cache_expired = True
                except (ValueError, TypeError):
                    station_cache_expired = True

            if station_cache_expired:
                self._stations = await self.hass.async_add_executor_job(
                    self.client.get_stations  # type: ignore[attr-defined]
                )
                codes = sorted(
                    [
                        c
                        for c in (getattr(s, "code", None) for s in self._stations)
                        if c is not None
                    ]
                )
                runtime_data["approved_station_codes"] = codes
                runtime_data["approved_station_codes_updated"] = now_utc.isoformat()
                if self.config_entry is not None:
                    self.config_entry.runtime_data = runtime_data
            else:
                codes = (
                    approved_station_codes if approved_station_codes is not None else []
                )
                # Only reconstruct self._stations if needed for downstream code
                if not self._stations:

                    class StationStub:
                        def __init__(self, code: str) -> None:
                            self.code = code

                    self._stations = [StationStub(code) for code in codes]

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
                    trips = await self.hass.async_add_executor_job(
                        self._get_trips_for_route, route
                    )
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
        except RequestParametersError as err:
            raise UpdateFailed(f"Invalid request parameters: {err}") from err
        else:
            return {
                ATTR_ROUTES: route_data,
                ATTR_STATIONS: self._stations,
            }

    def _get_trips_for_route(self, route: dict[str, Any]) -> list[Any]:
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
        # Use the stored approved station codes from runtime_data for validation
        valid_station_codes = set()
        if (
            self.config_entry is not None
            and hasattr(self.config_entry, "runtime_data")
            and self.config_entry.runtime_data
        ):
            valid_station_codes = set(
                self.config_entry.runtime_data.get("approved_station_codes", [])
            )
        if not valid_station_codes:
            # Fallback: build from stations if runtime_data is missing
            valid_station_codes = {
                code.upper()
                for s in self._stations
                for code in (
                    getattr(s, "code", None) if hasattr(s, "code") else s.get("code"),
                )
                if code
            }
        # Store approved station codes in runtime_data for use in config flow
        current_codes = []
        if (
            self.config_entry is not None
            and hasattr(self.config_entry, "runtime_data")
            and self.config_entry.runtime_data
        ):
            current_codes = self.config_entry.runtime_data.get(
                "approved_station_codes", []
            )
        # Always sort both lists before comparing and storing
        sorted_valid_codes = sorted(valid_station_codes)
        sorted_current_codes = sorted(current_codes)
        if sorted_valid_codes != sorted_current_codes:
            if self.config_entry is not None:
                if hasattr(self.config_entry, "runtime_data"):
                    self.config_entry.runtime_data["approved_station_codes"] = (
                        sorted_valid_codes
                    )
                else:
                    self.config_entry.runtime_data = {
                        "approved_station_codes": sorted_valid_codes
                    }
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
        trip_time_str = trip_time.strftime("%d-%m-%Y %H:%M")

        try:
            trips = self.client.get_trips(  # type: ignore[attr-defined]
                trip_time_str,
                from_station,
                via_station if via_station else None,
                to_station,
                True,  # departure
                0,  # previous
                2,  # next
            )
        except RequestParametersError as ex:
            _LOGGER.error("Error calling NSAPI.get_trips: %s", ex)
            return []
        # Filter out trips in the past (match official logic)
        future_trips = []
        for trip in trips or []:
            dep_time = trip.departure_time_actual or trip.departure_time_planned
            if dep_time and dep_time > now_nl:
                future_trips.append(trip)
        return future_trips

    async def async_add_route(self, route: dict[str, Any]) -> None:
        """Add a new route and trigger refresh, deduplicating by all properties."""
        if self.config_entry is None:
            return
        routes = list(self._get_routes())
        # Only add if not already present (deep equality)
        if route not in routes:
            routes.append(route)
            if self.config_entry is not None:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, options={CONF_ROUTES: routes}
                )
            await self.async_refresh()

    async def async_remove_route(self, route_name: str) -> None:
        """Remove a route and trigger refresh."""
        if self.config_entry is None:
            return
        routes = list(self._get_routes())
        routes = [r for r in routes if r.get(CONF_NAME) != route_name]
        self.hass.config_entries.async_update_entry(
            self.config_entry, options={CONF_ROUTES: routes}
        )
        await self.async_refresh()
