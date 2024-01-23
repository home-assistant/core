"""Exceptions for Google Tasks api calls."""

from homeassistant.exceptions import HomeAssistantError


class GoogleTasksApiError(HomeAssistantError):
    """Error talking to the Google Tasks API."""
