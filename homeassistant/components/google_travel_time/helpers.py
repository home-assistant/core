"""Helpers for Google Time Travel integration."""

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
    Location,
    RoutesAsyncClient,
    RouteTravelMode,
    Waypoint,
)
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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
    except (AttributeError, vol.Invalid):
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
