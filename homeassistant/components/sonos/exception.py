"""Sonos specific exceptions."""
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.exceptions import HomeAssistantError


class UnknownMediaType(BrowseError):
    """Unknown media type."""


class SpeakerUnavailable(HomeAssistantError):
    """Speaker is unavailable."""
