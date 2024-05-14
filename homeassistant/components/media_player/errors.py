"""Errors for the Media Player component."""

from homeassistant.exceptions import HomeAssistantError


class MediaPlayerException(HomeAssistantError):
    """Base class for Media Player exceptions."""


class BrowseError(MediaPlayerException):
    """Error while browsing."""
