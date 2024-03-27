"""Shared exceptions for the august integration."""

from homeassistant import exceptions


class UndefinedCEMError(exceptions.HomeAssistantError):
    """Error to indicate that the Customer Energy Manager has not been set up yet."""


class UnknownControlType(exceptions.HomeAssistantError):
    """Error to indicate that control type is unknown."""
