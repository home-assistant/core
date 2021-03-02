"""Sonos specific exceptions."""
from homeassistant.components.media_player.errors import BrowseError


class UnknownMediaType(BrowseError):
    """Unknown media type."""
