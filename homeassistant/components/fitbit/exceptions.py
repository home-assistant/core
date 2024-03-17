"""Exceptions for fitbit API calls.

These exceptions exist to provide common exceptions for the async and sync client libraries.
"""

from homeassistant.exceptions import HomeAssistantError


class FitbitApiException(HomeAssistantError):
    """Error talking to the fitbit API."""


class FitbitAuthException(FitbitApiException):
    """Authentication related error talking to the fitbit API."""
