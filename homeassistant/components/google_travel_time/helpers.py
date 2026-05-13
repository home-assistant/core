"""Helpers for Google Time Travel integration."""

import datetime
import logging

from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import (
    Forbidden,
    GatewayTimeout,
    GoogleAPIError,
    PermissionDenied,
    Unauthorized,
)
from google.maps.routing_v2 import (
    ComputeRoutesRequest,
    ComputeRoutesResponse,
    Location,
    RouteModifiers,
    RoutesAsyncClient,
    RouteTravelMode,
    RoutingPreference,
    TransitPreferences,
    Waypoint,
)
from google.protobuf import timestamp_pb2
from google.type import latlng_pb2
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.location import find_coordinates
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    TRAFFIC_MODELS_TO_GOOGLE_SDK_ENUM,
    TRANSIT_PREFS_TO_GOOGLE_SDK_ENUM,
    TRANSPORT_TYPES_TO_GOOGLE_SDK_ENUM,
    UNITS_TO_GOOGLE_SDK_ENUM,
)

_LOGGER = logging.getLogger(__name__)


def convert_time(time_str: str) -> timestamp_pb2.Timestamp:
    """Convert a string like '08:00' to a google pb2 Timestamp.

    If the time is in the past, it will be shifted to the next day.
    """
    parsed_time = dt_util.parse_time(time_str)
    if parsed_time is None:
        raise ValueError(f"Invalid time format: {time_str}")
    start_of_day = dt_util.start_of_local_day()
    combined = datetime.datetime.combine(
        start_of_day,
        parsed_time,
        start_of_day.tzinfo,
    )
    if combined < dt_util.now():
        combined = combined + datetime.timedelta(days=1)
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(dt=combined)
    return timestamp


def convert_to_waypoint(hass: HomeAssistant, location: str) -> Waypoint | None:
    """Convert a location to a Waypoint.

    Will either use coordinates or if none are found, use the location as an address.
    """
    coordinates = find_coordinates(hass, location)
    if coordinates is None:
        return None
    try:
        formatted_coordinates = coordinates.split(",")
        vol.Schema(cv.gps(formatted_coordinates))
    except AttributeError, vol.Invalid:
        return Waypoint(address=location)
    return Waypoint(
        location=Location(
            lat_lng=latlng_pb2.LatLng(
                latitude=float(formatted_coordinates[0]),
                longitude=float(formatted_coordinates[1]),
            )
        )
    )


async def validate_config_entry(
    hass: HomeAssistant, api_key: str, origin: str, destination: str
) -> None:
    """Return whether the config entry data is valid."""
    resolved_origin = convert_to_waypoint(hass, origin)
    resolved_destination = convert_to_waypoint(hass, destination)
    client_options = ClientOptions(api_key=api_key)
    client = RoutesAsyncClient(client_options=client_options)
    field_mask = "routes.duration"
    request = ComputeRoutesRequest(
        origin=resolved_origin,
        destination=resolved_destination,
        travel_mode=RouteTravelMode.DRIVE,
    )
    try:
        await client.compute_routes(
            request, metadata=[("x-goog-fieldmask", field_mask)]
        )
    except PermissionDenied as permission_error:
        _LOGGER.error("Permission denied: %s", permission_error.message)
        raise PermissionDeniedException from permission_error
    except (Unauthorized, Forbidden) as unauthorized_error:
        _LOGGER.error("Request denied: %s", unauthorized_error.message)
        raise InvalidApiKeyException from unauthorized_error
    except GatewayTimeout as timeout_error:
        _LOGGER.error("Timeout error")
        raise TimeoutError from timeout_error
    except GoogleAPIError as unknown_error:
        _LOGGER.error("Unknown error: %s", unknown_error)
        raise UnknownException from unknown_error


class InvalidApiKeyException(Exception):
    """Invalid API Key Error."""


class UnknownException(Exception):
    """Unknown API Error."""


class PermissionDeniedException(Exception):
    """Permission Denied Error."""


def create_routes_api_disabled_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create an issue for the Routes API being disabled."""
    async_create_issue(
        hass,
        DOMAIN,
        f"routes_api_disabled_{entry.entry_id}",
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
    client: RoutesAsyncClient,
    origin: str,
    destination: str,
    hass: HomeAssistant,
    travel_mode: int,
    units: str,
    language: str | None = None,
    avoid: str | None = None,
    traffic_model: str | None = None,
    transit_mode: str | None = None,
    transit_routing_preference: str | None = None,
    departure_time: str | None = None,
    arrival_time: str | None = None,
    field_mask: str = "routes.duration,routes.distanceMeters,routes.localized_values",
) -> ComputeRoutesResponse | None:
    """Compute routes using Google Routes API."""
    origin_waypoint = convert_to_waypoint(hass, origin)
    destination_waypoint = convert_to_waypoint(hass, destination)

    if origin_waypoint is None or destination_waypoint is None:
        return None

    route_modifiers = None
    routing_preference = None
    if travel_mode == RouteTravelMode.DRIVE:
        routing_preference = RoutingPreference.TRAFFIC_AWARE_OPTIMAL
        route_modifiers = RouteModifiers(
            avoid_tolls=avoid == "tolls",
            avoid_ferries=avoid == "ferries",
            avoid_highways=avoid == "highways",
            avoid_indoor=avoid == "indoor",
        )

    transit_preferences = None
    if travel_mode == RouteTravelMode.TRANSIT:
        transit_routing_pref = None
        transit_travel_mode = (
            TransitPreferences.TransitTravelMode.TRANSIT_TRAVEL_MODE_UNSPECIFIED
        )
        if transit_routing_preference is not None:
            transit_routing_pref = TRANSIT_PREFS_TO_GOOGLE_SDK_ENUM[
                transit_routing_preference
            ]
        if transit_mode is not None:
            transit_travel_mode = TRANSPORT_TYPES_TO_GOOGLE_SDK_ENUM[transit_mode]
        transit_preferences = TransitPreferences(
            routing_preference=transit_routing_pref,
            allowed_travel_modes=[transit_travel_mode],
        )

    departure_timestamp = convert_time(departure_time) if departure_time else None
    arrival_timestamp = convert_time(arrival_time) if arrival_time else None

    request = ComputeRoutesRequest(
        origin=origin_waypoint,
        destination=destination_waypoint,
        travel_mode=travel_mode,
        routing_preference=routing_preference,
        departure_time=departure_timestamp,
        arrival_time=arrival_timestamp,
        route_modifiers=route_modifiers,
        language_code=language,
        units=UNITS_TO_GOOGLE_SDK_ENUM[units],
        traffic_model=TRAFFIC_MODELS_TO_GOOGLE_SDK_ENUM[traffic_model]
        if traffic_model
        else None,
        transit_preferences=transit_preferences,
    )

    return await client.compute_routes(
        request, metadata=[("x-goog-fieldmask", field_mask)]
    )
