"""Snapcast Integration."""
from dataclasses import dataclass

from snapcast.control import Snapserver

from homeassistant.components.media_player import MediaPlayerEntity


@dataclass
class HomeAssistantSnapcast:
    """Snapcast data stored in the Home Assistant data object."""

    server: Snapserver
    clients: list[MediaPlayerEntity]
    groups: list[MediaPlayerEntity]
