"""Exceptions to the co2signal integration."""
from homeassistant.exceptions import HomeAssistantError


class CO2Error(HomeAssistantError):
    """Base error."""


class InvalidAuth(CO2Error):
    """Raised when invalid authentication credentials are provided."""


class APIRatelimitExceeded(CO2Error):
    """Raised when the API rate limit is exceeded."""


class UnknownError(CO2Error):
    """Raised when an unknown error occurs."""
