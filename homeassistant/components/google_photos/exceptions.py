"""Exceptions for Google Photos api calls."""

from homeassistant.exceptions import HomeAssistantError


class GooglePhotosApiError(HomeAssistantError):
    """Error talking to the Google Photos API."""
