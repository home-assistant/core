"""Errors for media source."""

from homeassistant.exceptions import HomeAssistantError


class MediaSourceError(HomeAssistantError):
    """Base class for media source errors."""


class Unresolvable(MediaSourceError):
    """When media ID is not resolvable."""


class UnknownMediaSource(MediaSourceError, ValueError):
    """When media source is unknown."""
