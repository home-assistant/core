"""Custom exceptions for the devolo_home_control integration."""

from homeassistant.exceptions import HomeAssistantError


class CredentialsInvalid(HomeAssistantError):
    """Given credentials are invalid."""


class UuidChanged(HomeAssistantError):
    """UUID of the user changed."""
