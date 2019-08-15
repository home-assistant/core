"""Errors for the Plex component."""
from homeassistant.exceptions import HomeAssistantError


class PlexException(HomeAssistantError):
    """Base class for Plex exceptions."""


class ConfigNotReady(PlexException):
    """Not enough configuration provided to attempt connection."""


class NoServersFound(PlexException):
    """No servers found on Plex account."""
