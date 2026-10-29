"""Helpers for Google Time Travel integration."""

import datetime as dt
import logging

from google_maps_routing_api import (
    ComputeRoutesResponse,
    GoogleMapsRoutingApi,
    GoogleMapsRoutingApiAuthError,
    GoogleMapsRoutingApiConnectionTimeoutError,
    GoogleMapsRoutingApiError,
    LatLng,
    LocalizedText,
    Location,
    RoutingPreference,
    TransitTravelMode,
    TravelMode,
    Waypoint,
)
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

from .const import (
    DOMAIN,
    TRAFFIC_MODELS_TO_API_ENUM,
    TRANSIT_PREFS_TO_API_ENUM,
    TRANSPORT_TYPES_TO_API_ENUM,
    UNITS_TO_API_ENUM,
)

_LOGGER = logging.getLogger(__name__)

CLIENT_TIMEOUT = 30


def get_client(hass: HomeAssistant, api_key: str) -> GoogleMapsRoutingApi:
    """Return a Google Maps Routes API client."""
    return GoogleMapsRoutingApi(
        session=async_get_clientsession(hass),
        api_key=api_key,
        timeout=CLIENT_TIMEOUT,
    )


def is_routes_api_disabled(err: GoogleMapsRoutingApiAuthError) -> bool:
    """Return whether the Routes API can't be used with this API key.

    This is a permission denied error (HTTP 403), such as the API not being enabled
    or being excluded by the API key restrictions.
    """
    return err.status == "PERMISSION_DENIED"


def convert_time(time_str: str) -> dt.datetime:
    """Convert a string like '08:00' to a datetime.

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
    return combined


def convert_to_waypoint(hass: HomeAssistant, location: str) -> Waypoint | None:
    """Convert a location to a Waypoint.

    Will either use coordinates or if none are found, use the location as an address.
    """
    coordinates = find_coordinates(hass, location)
    if coordinates is None:
        return None
    try:
        formatted_coordinates = coordinates.split(",")
        probatio.Schema(cv.gps(formatted_coordinates))
    except AttributeError, probatio.Invalid:
        return Waypoint(address=location)
    return Waypoint(
        location=Location(
            lat_lng=LatLng(
                latitude=float(formatted_coordinates[0]),
                longitude=float(formatted_coordinates[1]),
            )
        )
    )


def get_localized_text(text: LocalizedText | None) -> str:
    """Return the localized text, or an empty string when it is missing."""
    if text is None or text.text is None:
        return ""
    return text.text


async def validate_config_entry(
    hass: HomeAssistant,
    api_key: str,
    origin: str,
    destination: str,
) -> None:
    """Validate the config entry data."""
    origin_waypoint = convert_to_waypoint(hass, origin)
    destination_waypoint = convert_to_waypoint(hass, destination)
    if origin_waypoint is None or destination_waypoint is None:
        raise UnknownException("Unable to resolve the origin or destination")

    client = get_client(hass, api_key)
    try:
        await client.async_compute_routes(
            origin=origin_waypoint,
            destination=destination_waypoint,
            travel_mode=TravelMode.DRIVE,
            field_mask="routes.duration",
        )
    except GoogleMapsRoutingApiAuthError as auth_error:
        if is_routes_api_disabled(auth_error):
            _LOGGER.error("Routes API is disabled: %s", auth_error)
            raise PermissionDeniedException from auth_error
        _LOGGER.error("Request denied: %s", auth_error)
        raise InvalidApiKeyException from auth_error
    except GoogleMapsRoutingApiConnectionTimeoutError as timeout_error:
        _LOGGER.error("Timeout error")
        raise TimeoutError from timeout_error
    except GoogleMapsRoutingApiError as unknown_error:
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
    client: GoogleMapsRoutingApi,
    origin: str,
    destination: str,
    hass: HomeAssistant,
    travel_mode: TravelMode,
    units: str,
    language: str | None = None,
    avoid: str | None = None,
    traffic_model: str | None = None,
    transit_mode: str | None = None,
    transit_routing_preference: str | None = None,
    departure_time: str | None = None,
    arrival_time: str | None = None,
    field_mask: str = (
        "routes.duration,routes.staticDuration,routes.distanceMeters,routes.localizedValues"
    ),
) -> ComputeRoutesResponse | None:
    """Compute routes using Google Routes API."""
    origin_waypoint = convert_to_waypoint(hass, origin)
    destination_waypoint = convert_to_waypoint(hass, destination)

    if origin_waypoint is None or destination_waypoint is None:
        return None

    routing_preference = None
    avoid_tolls = avoid_highways = avoid_ferries = avoid_indoor = False
    if travel_mode == TravelMode.DRIVE:
        routing_preference = RoutingPreference.TRAFFIC_AWARE_OPTIMAL
        avoid_tolls = avoid == "tolls"
        avoid_ferries = avoid == "ferries"
        avoid_highways = avoid == "highways"
        avoid_indoor = avoid == "indoor"

    transit_routing_preference_enum = None
    allowed_travel_modes: list[TransitTravelMode | str] | None = None
    if travel_mode == TravelMode.TRANSIT:
        if transit_routing_preference is not None:
            transit_routing_preference_enum = TRANSIT_PREFS_TO_API_ENUM[
                transit_routing_preference
            ]
        if transit_mode is not None:
            allowed_travel_modes = [TRANSPORT_TYPES_TO_API_ENUM[transit_mode]]

    return await client.async_compute_routes(
        origin=origin_waypoint,
        destination=destination_waypoint,
        travel_mode=travel_mode,
        routing_preference=routing_preference,
        departure_time=convert_time(departure_time) if departure_time else None,
        arrival_time=convert_time(arrival_time) if arrival_time else None,
        language_code=language,
        units=UNITS_TO_API_ENUM[units],
        avoid_tolls=avoid_tolls,
        avoid_highways=avoid_highways,
        avoid_ferries=avoid_ferries,
        avoid_indoor=avoid_indoor,
        traffic_model=TRAFFIC_MODELS_TO_API_ENUM[traffic_model]
        if traffic_model
        else None,
        transit_routing_preference=transit_routing_preference_enum,
        allowed_travel_modes=allowed_travel_modes,
        field_mask=field_mask,
    )
