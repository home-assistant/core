"""Errors for the deCONZ component."""
from homeassistant.exceptions import HomeAssistantError


class DeconzException(HomeAssistantError):
    """Base class for deCONZ exceptions."""


class AlreadyConfigured(DeconzException):
    """Gateway is already configured."""


class AuthenticationRequired(DeconzException):
    """Unknown error occurred."""


class CannotConnect(DeconzException):
    """Unable to connect to the gateway."""
