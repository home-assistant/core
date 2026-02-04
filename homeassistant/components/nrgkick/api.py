"""Home Assistant exceptions for the NRGkick integration."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


class NRGkickApiClientError(HomeAssistantError):
    """Base exception for NRGkick API client errors."""

    translation_domain = DOMAIN
    translation_key = "unknown_error"


class NRGkickApiClientCommunicationError(NRGkickApiClientError):
    """Exception for NRGkick API client communication errors."""

    translation_domain = DOMAIN
    translation_key = "communication_error"


class NRGkickApiClientAuthenticationError(NRGkickApiClientError):
    """Exception for NRGkick API client authentication errors."""

    translation_domain = DOMAIN
    translation_key = "authentication_error"


class NRGkickApiClientApiDisabledError(NRGkickApiClientError):
    """Exception for disabled NRGkick JSON API."""

    translation_domain = DOMAIN
    translation_key = "json_api_disabled"


class NRGkickApiClientInvalidResponseError(NRGkickApiClientError):
    """Exception for invalid responses from the device."""
