"""Exceptions for the dwd_weather_warnings integration."""

from homeassistant.exceptions import HomeAssistantError


class EntityNotFoundError(HomeAssistantError):
    """When a referenced entity was not found."""


class CoordinatesNotFoundError(HomeAssistantError):
    """When coordinates for a referenced entity were not found."""
