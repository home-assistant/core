"""Errors for the Swisscom component."""
from homeassistant.exceptions import HomeAssistantError


class SwisscomException(HomeAssistantError):
    """Base class for Swisscom exceptions."""


class CannotLoginException(SwisscomException):
    """Unable to login to the router."""
