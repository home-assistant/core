"""Errors for NOAA Tides integration."""

from homeassistant.exceptions import HomeAssistantError


class NoaaTidesException(HomeAssistantError):
    """Base class for NOAA Tides exceptions."""


class StationNotFound(NoaaTidesException):
    """Station not found exception."""
