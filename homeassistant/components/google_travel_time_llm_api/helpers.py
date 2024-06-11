"""Helpers for Google Time Travel integration."""

import logging

from googlemaps import Client

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def validate_config_entry(hass: HomeAssistant, api_key: str) -> None:
    """Return whether the config entry data is valid."""
    try:
        Client(api_key, timeout=10)
    except ValueError as value_error:
        _LOGGER.error("Malformed API key")
        raise InvalidApiKeyException from value_error


class InvalidApiKeyException(Exception):
    """Invalid API Key Error."""
