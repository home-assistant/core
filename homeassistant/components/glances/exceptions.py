"""Exceptions raised by glances integration."""

from homeassistant.exceptions import HomeAssistantError


class GlancesError(HomeAssistantError):
    """Base class for glances exceptions."""


class CannotConnect(GlancesError):
    """Error to indicate we cannot connect."""


class AuthorizationError(GlancesError):
    """Error raised when unauthorized."""
