"""API wrapper for Nederlandse Spoorwegen integration."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
import zoneinfo

import ns_api
from ns_api import NSAPI
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    HTTPError,
    Timeout,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


def get_ns_api_version() -> str:
    """Get the version of the ns_api library."""
    return ns_api.__version__


class NSAPIError(HomeAssistantError):
    """Base exception for NS API errors."""


class NSAPIAuthError(NSAPIError):
    """Exception for authentication errors."""


class NSAPIConnectionError(NSAPIError):
    """Exception for connection errors."""


class NSAPIWrapper:
    """Wrapper for NS API interactions."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize the NS API wrapper."""
        self.hass = hass
        self._client = NSAPI(api_key)

    async def validate_api_key(self) -> bool:
        """Validate the API key by attempting to fetch stations.

        Returns:
            True if API key is valid.

        Raises:
            NSAPIAuthError: If authentication fails.
            NSAPIConnectionError: If connection fails.
            NSAPIError: For other API errors.
        """
        try:
            await self.hass.async_add_executor_job(self._client.get_stations)
        except HTTPError as ex:
            _LOGGER.debug("API validation failed with HTTP error: %s", ex)
            if ex.response and ex.response.status_code == 401:
                raise NSAPIAuthError("Invalid API key") from ex
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except (RequestsConnectionError, Timeout) as ex:
            _LOGGER.debug("API validation failed with connection error: %s", ex)
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except ValueError as ex:
            # ns_api library sometimes raises ValueError for auth issues
            _LOGGER.debug("API validation failed with ValueError: %s", ex)
            # No string parsing - treat ValueError as connection error
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        else:
            return True

    async def get_stations(self) -> list[Any]:
        """Get all available stations.

        Returns:
            List of station objects.

        Raises:
            NSAPIAuthError: If authentication fails.
            NSAPIConnectionError: If connection fails.
            NSAPIError: For other API errors.
        """
        try:
            stations = await self.hass.async_add_executor_job(self._client.get_stations)
        except HTTPError as ex:
            _LOGGER.warning("Failed to get stations - HTTP error: %s", ex)
            if ex.response and ex.response.status_code == 401:
                raise NSAPIAuthError("Invalid API key") from ex
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except (RequestsConnectionError, Timeout) as ex:
            _LOGGER.warning("Failed to get stations - Connection error: %s", ex)
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except ValueError as ex:
            _LOGGER.warning("Failed to get stations - ValueError: %s", ex)
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        else:
            _LOGGER.debug("Retrieved %d stations from NS API", len(stations))
            return stations

    async def get_trips(
        self,
        from_station: str,
        to_station: str,
        via_station: str | None = None,
        departure_time: datetime | None = None,
    ) -> list[Any]:
        """Get trip information between stations.

        Args:
            from_station: Origin station code.
            to_station: Destination station code.
            via_station: Optional via station code.
            departure_time: Optional departure time.

        Returns:
            List of trip objects.

        Raises:
            NSAPIAuthError: If authentication fails.
            NSAPIConnectionError: If connection fails.
            NSAPIError: For other API errors.
        """
        try:
            # Create a partial function to handle optional parameters
            def _get_trips():
                # Convert datetime to string format expected by NSAPI
                timestamp_str = None
                if departure_time:
                    # NSAPI expects format: 'dd-mm-yyyy HH:MM'
                    timestamp_str = departure_time.strftime("%d-%m-%Y %H:%M")

                return self._client.get_trips(
                    timestamp=timestamp_str,
                    start=from_station,
                    via=via_station,
                    destination=to_station,
                )

            trips = await self.hass.async_add_executor_job(_get_trips)
        except ValueError as ex:
            _LOGGER.warning(
                "Failed to get trips from %s to %s - ValueError: %s",
                from_station,
                to_station,
                ex,
            )
            if (
                "401" in str(ex)
                or "unauthorized" in str(ex).lower()
                or "invalid" in str(ex).lower()
            ):
                raise NSAPIAuthError("Invalid API key") from ex
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except (ConnectionError, TimeoutError) as ex:
            _LOGGER.warning(
                "Failed to get trips from %s to %s - Connection error: %s",
                from_station,
                to_station,
                ex,
            )
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except Exception as ex:
            _LOGGER.warning(
                "Failed to get trips from %s to %s - Unexpected error: %s",
                from_station,
                to_station,
                ex,
            )
            raise NSAPIError(f"Unexpected error getting trips: {ex}") from ex
        else:
            if trips is None:
                trips = []

            # Filter out trips in the past
            future_trips = self._filter_future_trips(trips)

            _LOGGER.debug(
                "Retrieved %d trips from %s to %s, %d future trips after filtering",
                len(trips),
                from_station,
                to_station,
                len(future_trips),
            )
            return future_trips

    async def get_departures(
        self,
        station: str,
        departure_time: datetime | None = None,
        max_journeys: int | None = None,
    ) -> list[Any]:
        """Get departure information for a station.

        Args:
            station: Station code.
            departure_time: Optional departure time.
            max_journeys: Optional maximum number of journeys.

        Returns:
            List of departure objects.

        Raises:
            NSAPIAuthError: If authentication fails.
            NSAPIConnectionError: If connection fails.
            NSAPIError: For other API errors.
        """
        try:
            # Create a partial function to handle optional parameters
            def _get_departures():
                kwargs = {}
                if departure_time:
                    kwargs["datetime"] = departure_time
                if max_journeys:
                    kwargs["max_journeys"] = max_journeys
                return self._client.get_departures(station, **kwargs)

            departures = await self.hass.async_add_executor_job(_get_departures)
        except ValueError as ex:
            _LOGGER.warning(
                "Failed to get departures for %s - ValueError: %s", station, ex
            )
            if (
                "401" in str(ex)
                or "unauthorized" in str(ex).lower()
                or "invalid" in str(ex).lower()
            ):
                raise NSAPIAuthError("Invalid API key") from ex
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except (ConnectionError, TimeoutError) as ex:
            _LOGGER.warning(
                "Failed to get departures for %s - Connection error: %s", station, ex
            )
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except Exception as ex:
            _LOGGER.warning(
                "Failed to get departures for %s - Unexpected error: %s", station, ex
            )
            raise NSAPIError(f"Unexpected error getting departures: {ex}") from ex
        else:
            if departures is None:
                departures = []
            _LOGGER.debug(
                "Retrieved %d departures for station %s", len(departures), station
            )
            return departures

    async def get_disruptions(self, station: str | None = None) -> Any:
        """Get disruption information.

        Args:
            station: Optional station code to filter disruptions.

        Returns:
            Disruption data (format varies by API).

        Raises:
            NSAPIAuthError: If authentication fails.
            NSAPIConnectionError: If connection fails.
            NSAPIError: For other API errors.
        """
        try:
            # Create a partial function to handle optional parameters
            def _get_disruptions():
                kwargs = {}
                if station:
                    kwargs["station"] = station
                return self._client.get_disruptions(**kwargs)

            disruptions = await self.hass.async_add_executor_job(_get_disruptions)
        except ValueError as ex:
            _LOGGER.warning("Failed to get disruptions - ValueError: %s", ex)
            if (
                "401" in str(ex)
                or "unauthorized" in str(ex).lower()
                or "invalid" in str(ex).lower()
            ):
                raise NSAPIAuthError("Invalid API key") from ex
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except (ConnectionError, TimeoutError) as ex:
            _LOGGER.warning("Failed to get disruptions - Connection error: %s", ex)
            raise NSAPIConnectionError("Failed to connect to NS API") from ex
        except Exception as ex:
            _LOGGER.warning("Failed to get disruptions - Unexpected error: %s", ex)
            raise NSAPIError(f"Unexpected error getting disruptions: {ex}") from ex
        else:
            _LOGGER.debug("Retrieved disruptions data")
            return disruptions

    def build_station_mapping(self, stations: list[Any]) -> dict[str, str]:
        """Build a mapping of station codes to names from station data.

        Args:
            stations: List of station objects from the API.

        Returns:
            Dictionary mapping station codes to names.
        """
        station_mapping = {}

        for station in stations:
            try:
                code = None
                name = None

                if hasattr(station, "code") and hasattr(station, "name"):
                    # Standard format: separate code and name attributes
                    code = getattr(station, "code", None)
                    name = getattr(station, "name", None)
                elif isinstance(station, dict):
                    # Dict format
                    code = station.get("code")
                    name = station.get("name")
                else:
                    # Handle string format or object with __str__ method
                    station_str = str(station)

                    # Validate string is reasonable length and contains expected chars
                    if not station_str or len(station_str) > 200:
                        _LOGGER.debug(
                            "Skipping invalid station string: length %d",
                            len(station_str),
                        )
                        continue

                    # Remove class name wrapper if present
                    # (e.g., "<Station> AC Abcoude" -> "AC Abcoude")
                    if station_str.startswith("<") and "> " in station_str:
                        try:
                            station_str = station_str.split("> ", 1)[1]
                        except IndexError:
                            _LOGGER.debug(
                                "Skipping malformed station string: %s",
                                station_str[:50],
                            )
                            continue

                    # Try to parse "CODE Name" format with proper validation
                    parts = station_str.strip().split(" ", 1)
                    if len(parts) == 2 and parts[0] and parts[1]:
                        potential_code = parts[0].strip()
                        potential_name = parts[1].strip()

                        # Validate code format (should be reasonable station code)
                        if (
                            potential_code.isalnum()
                            and 1 <= len(potential_code) <= 10
                            and potential_name
                            and len(potential_name) <= 100
                        ):
                            code = potential_code
                            name = potential_name
                        else:
                            _LOGGER.debug(
                                "Skipping invalid station format: %s", station_str[:50]
                            )
                            continue
                    else:
                        _LOGGER.debug(
                            "Skipping unparsable station string: %s", station_str[:50]
                        )
                        continue

                # Only add if we have both valid code and name
                if (
                    code
                    and name
                    and isinstance(code, str)
                    and isinstance(name, str)
                    and code.strip()
                    and name.strip()
                ):
                    station_mapping[code.upper().strip()] = name.strip()
                else:
                    _LOGGER.debug(
                        "Skipping station with missing code or name: code=%s, name=%s",
                        code,
                        name,
                    )

            except (AttributeError, TypeError, ValueError) as ex:
                _LOGGER.debug("Error processing station %s: %s", station, ex)
                continue

        _LOGGER.debug("Built station mapping with %d stations", len(station_mapping))
        return station_mapping

    def get_station_codes(self, stations: list[Any]) -> set[str]:
        """Get valid station codes from station data.

        Args:
            stations: List of station objects from the API.

        Returns:
            Set of valid station codes (uppercase).
        """
        station_mapping = self.build_station_mapping(stations)
        return set(station_mapping.keys())

    def _filter_future_trips(self, trips: list[Any]) -> list[Any]:
        """Filter out trips that have already departed.

        Args:
            trips: List of trip objects from NS API.

        Returns:
            List of trips with departure time in the future.
        """
        if not trips:
            return []

        # Get current time in Netherlands timezone
        nl_tz = zoneinfo.ZoneInfo("Europe/Amsterdam")
        now_nl = dt_util.now(nl_tz)

        future_trips = []
        for trip in trips:
            # Use actual departure time if available, otherwise planned time
            dep_time = trip.departure_time_actual or trip.departure_time_planned
            if dep_time and dep_time > now_nl:
                future_trips.append(trip)

        _LOGGER.debug(
            "Filtered %d past trips, %d future trips remaining",
            len(trips) - len(future_trips),
            len(future_trips),
        )
        return future_trips

    @staticmethod
    def normalize_station_code(station_code: str | None) -> str:
        """Normalize station code to uppercase for consistent handling.

        Args:
            station_code: Station code to normalize.

        Returns:
            Normalized station code (uppercase) or empty string if None.
        """
        if not station_code:
            return ""
        return station_code.upper().strip()
