"""Errors for the Konnected component."""

from homeassistant.exceptions import HomeAssistantError


class KonnectedException(HomeAssistantError):
    """Base class for Konnected exceptions."""


class CannotConnect(KonnectedException):
    """Unable to connect to the panel."""
