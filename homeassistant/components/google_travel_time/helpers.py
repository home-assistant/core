"""Helpers for Google Time Travel integration."""

import logging

from googlemaps import Client
from googlemaps.distance_matrix import distance_matrix
from googlemaps.exceptions import ApiError, Timeout, TransportError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.location import find_coordinates

_LOGGER = logging.getLogger(__name__)


def validate_config_entry(
    hass: HomeAssistant, api_key: str, origin: str, destination: str
) -> None:
    """Return whether the config entry data is valid."""
    resolved_origin = find_coordinates(hass, origin)
    resolved_destination = find_coordinates(hass, destination)
    try:
        client = Client(api_key, timeout=10)
    except ValueError as value_error:
        _LOGGER.error("Malformed API key")
        raise InvalidApiKeyException from value_error
    try:
        distance_matrix(client, resolved_origin, resolved_destination, mode="driving")
    except ApiError as api_error:
        if api_error.status == "REQUEST_DENIED":
            _LOGGER.error("Request denied: %s", api_error.message)
            raise InvalidApiKeyException from api_error
        _LOGGER.error("Unknown error: %s", api_error.message)
        raise UnknownException from api_error
    except TransportError as transport_error:
        _LOGGER.error("Unknown error: %s", transport_error)
        raise UnknownException from transport_error
    except Timeout as timeout_error:
        _LOGGER.error("Timeout error")
        raise TimeoutError from timeout_error


class InvalidApiKeyException(Exception):
    """Invalid API Key Error."""


class UnknownException(Exception):
    """Unknown API Error."""
