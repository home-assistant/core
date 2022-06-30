"""Sonos specific exceptions."""
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.exceptions import HomeAssistantError


class UnknownMediaType(BrowseError):
    """Unknown media type."""


class SonosUpdateError(HomeAssistantError):
    """Update failed."""
