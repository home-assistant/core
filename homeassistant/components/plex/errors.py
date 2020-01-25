"""Errors for the Plex component."""
from homeassistant.exceptions import HomeAssistantError


class PlexException(HomeAssistantError):
    """Base class for Plex exceptions."""


class NoServersFound(PlexException):
    """No servers found on Plex account."""


class ServerNotSpecified(PlexException):
    """Multiple servers linked to account without choice provided."""
