"""Errors for the Hue component."""

from homeassistant.exceptions import HomeAssistantError


class HueException(HomeAssistantError):
    """Base class for Hue exceptions."""


class CannotConnect(HueException):
    """Unable to connect to the bridge."""


class AuthenticationRequired(HueException):
    """Unknown error occurred."""
