"""Helpers for Google Travel Time integration."""

from dataclasses import dataclass
import datetime as dt
from typing import Any, NoReturn

import aiohttp
import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.location import find_coordinates
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads

from .const import (
    DOMAIN,
    TRAFFIC_MODELS_TO_API,
    TRANSIT_PREFS_TO_API,
    TRANSPORT_TYPES_TO_API,
    UNITS_TO_API,
)

COMPUTE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=30)


class GoogleAPIError(Exception):
    """Error returned by the Google Routes API."""


class PermissionDenied(GoogleAPIError):
    """The API key is not allowed to use the Routes API."""


class InvalidApiKeyException(GoogleAPIError):
    """The API key is invalid."""


class InvalidReferrerException(GoogleAPIError):
    """The HTTP referrer is not allowed for the API key."""


@dataclass(slots=True)
class Route:
    """A route returned by the Compute Routes API."""

    duration_seconds: int
    distance_meters: int
    duration_text: str
    static_duration_text: str
    distance_text: str


@dataclass(slots=True)
class ComputeRoutesResponse:
    """Response of the Compute Routes API."""

    routes: list[Route]


def _parse_duration_seconds(duration: str | None) -> int:
    """Convert a duration such as 534s to seconds."""
    if not duration:
        return 0
    return int(float(duration.removesuffix("s")))


def _parse_routes_response(data: dict[str, Any]) -> ComputeRoutesResponse:
    """Convert a Compute Routes API response to a typed response."""
    routes = []
    for route in data.get("routes", []):
        localized_values = route.get("localizedValues", {})
        routes.append(
            Route(
                duration_seconds=_parse_duration_seconds(route.get("duration")),
                distance_meters=route.get("distanceMeters", 0),
                duration_text=localized_values.get("duration", {}).get("text", ""),
                static_duration_text=localized_values.get("staticDuration", {}).get(
                    "text", ""
                ),
                distance_text=localized_values.get("distance", {}).get("text", ""),
            )
        )
    return ComputeRoutesResponse(routes=routes)


def _get_error_reason(error: dict[str, Any]) -> str | None:
    """Return the reason of a Google API error."""
    for detail in error.get("details", []):
        if reason := detail.get("reason"):
            return reason
    return None


def _raise_api_error(status: int, body: str) -> NoReturn:
    """Raise an exception for an unsuccessful API response."""
    error: dict[str, Any] = {}
    try:
        parsed = json_loads(body)
    except ValueError:
        parsed = None
    error_data = parsed.get("error") if isinstance(parsed, dict) else None
    if isinstance(error_data, dict):
        error = error_data
    message = error.get("message") or body
    reason = _get_error_reason(error)
    if status == 401 or reason == "API_KEY_INVALID":
        raise InvalidApiKeyException(message)
    if reason == "API_KEY_HTTP_REFERRER_BLOCKED":
        raise InvalidReferrerException(message)
    if status == 403:
        raise PermissionDenied(message)
    if status == 504:
        raise TimeoutError(message)
    raise GoogleAPIError(message)


class RoutesClient:
    """Client for the Google Routes API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        referrer: str | None = None,
    ) -> None:
        """Initialize the client."""
        self._session = async_get_clientsession(hass)
        self._api_key = api_key
        self._referrer = referrer

    async def compute_routes(
        self, payload: dict[str, Any], field_mask: str
    ) -> ComputeRoutesResponse:
        """Compute routes."""
        headers: dict[str, str] = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": field_mask,
        }
        if self._referrer:
            headers["Referer"] = self._referrer

        try:
            async with self._session.post(
                COMPUTE_ROUTES_URL,
                json=payload,
                headers=headers,
                timeout=CLIENT_TIMEOUT,
            ) as response:
                status = response.status
                body = await response.text()
        except TimeoutError as err:
            raise TimeoutError("Timeout connecting to the Google Routes API") from err
        except aiohttp.ClientError as err:
            raise GoogleAPIError(str(err)) from err

        if status >= 400:
            _raise_api_error(status, body)

        if not body:
            return ComputeRoutesResponse(routes=[])

        try:
            data = json_loads(body)
        except ValueError as err:
            raise GoogleAPIError("Invalid response from the Google Routes API") from err
        if not isinstance(data, dict):
            raise GoogleAPIError("Invalid response from the Google Routes API")
        return _parse_routes_response(data)


def convert_time(time_str: str) -> str:
    """Convert a string like '08:00' to an RFC 3339 timestamp.

    If the time is in the past, it will be shifted to the next day.
    """
    parsed_time = dt_util.parse_time(time_str)
    if parsed_time is None:
        raise ValueError(f"Invalid time format: {time_str}")
    start_of_day = dt_util.start_of_local_day()
    combined = dt.datetime.combine(
        start_of_day,
        parsed_time,
        start_of_day.tzinfo,
    )
    if combined < dt_util.now():
        combined = combined + dt.timedelta(days=1)
    return dt_util.as_utc(combined).isoformat().replace("+00:00", "Z")


def convert_to_waypoint(hass: HomeAssistant, location: str) -> dict[str, Any] | None:
    """Convert a location to a waypoint.

    Will either use coordinates or if none are found, use the location as an address.
    """
    coordinates = find_coordinates(hass, location)
    if coordinates is None:
        return None
    try:
        formatted_coordinates = coordinates.split(",")
        probatio.Schema(cv.gps(formatted_coordinates))
    except AttributeError, probatio.Invalid:
        return {"address": location}
    return {
        "location": {
            "latLng": {
                "latitude": float(formatted_coordinates[0]),
                "longitude": float(formatted_coordinates[1]),
            }
        }
    }


async def validate_config_entry(
    hass: HomeAssistant,
    api_key: str,
    origin: str,
    destination: str,
    referrer: str | None = None,
) -> None:
    """Return whether the config entry data is valid."""
    client = RoutesClient(hass, api_key, referrer)
    await client.compute_routes(
        {
            "origin": convert_to_waypoint(hass, origin),
            "destination": convert_to_waypoint(hass, destination),
            "travelMode": "DRIVE",
        },
        field_mask="routes.duration",
    )


def create_routes_api_disabled_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create an issue for the Routes API being disabled."""
    async_create_issue(
        hass,
        DOMAIN,
        f"routes_api_disabled_{entry.entry_id}",
        config_entry_id=entry.entry_id,
        learn_more_url="https://www.home-assistant.io/integrations/google_travel_time#setup",
        is_fixable=False,
        severity=IssueSeverity.ERROR,
        translation_key="routes_api_disabled",
        translation_placeholders={
            "entry_title": entry.title,
            "enable_api_url": "https://cloud.google.com/endpoints/docs/openapi/enable-api",
            "api_key_restrictions_url": "https://cloud.google.com/docs/authentication/api-keys#adding-api-restrictions",
        },
    )


def delete_routes_api_disabled_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the issue for the Routes API being disabled."""
    async_delete_issue(hass, DOMAIN, f"routes_api_disabled_{entry.entry_id}")


async def async_compute_routes(
    client: RoutesClient,
    origin: str,
    destination: str,
    hass: HomeAssistant,
    travel_mode: str,
    units: str,
    language: str | None = None,
    avoid: str | None = None,
    traffic_model: str | None = None,
    transit_mode: str | None = None,
    transit_routing_preference: str | None = None,
    departure_time: str | None = None,
    arrival_time: str | None = None,
    field_mask: str = "routes.duration,routes.distanceMeters,routes.localizedValues",
) -> ComputeRoutesResponse | None:
    """Compute routes using Google Routes API."""
    origin_waypoint = convert_to_waypoint(hass, origin)
    destination_waypoint = convert_to_waypoint(hass, destination)

    if origin_waypoint is None or destination_waypoint is None:
        return None

    payload: dict[str, Any] = {
        "origin": origin_waypoint,
        "destination": destination_waypoint,
        "travelMode": travel_mode,
        "units": UNITS_TO_API[units],
    }

    if travel_mode == "DRIVE":
        payload["routingPreference"] = "TRAFFIC_AWARE_OPTIMAL"
        payload["routeModifiers"] = {
            "avoidTolls": avoid == "tolls",
            "avoidFerries": avoid == "ferries",
            "avoidHighways": avoid == "highways",
            "avoidIndoor": avoid == "indoor",
        }
    elif travel_mode == "TRANSIT":
        transit_preferences: dict[str, Any] = {}
        if transit_routing_preference is not None:
            transit_preferences["routingPreference"] = TRANSIT_PREFS_TO_API[
                transit_routing_preference
            ]
        if transit_mode is not None:
            transit_preferences["allowedTravelModes"] = [
                TRANSPORT_TYPES_TO_API[transit_mode]
            ]
        if transit_preferences:
            payload["transitPreferences"] = transit_preferences

    if departure_time:
        payload["departureTime"] = convert_time(departure_time)
    if arrival_time:
        payload["arrivalTime"] = convert_time(arrival_time)
    if language:
        payload["languageCode"] = language
    if traffic_model:
        payload["trafficModel"] = TRAFFIC_MODELS_TO_API[traffic_model]

    return await client.compute_routes(payload, field_mask=field_mask)
