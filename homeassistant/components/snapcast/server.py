"""Snapcast Integration."""
from dataclasses import dataclass, field

from snapcast.control import Snapserver

from homeassistant.components.media_player import MediaPlayerEntity


@dataclass
class HomeAssistantSnapcast:
    """Snapcast data stored in the Home Assistant data object."""

    server: Snapserver
    clients: list[MediaPlayerEntity] = field(default_factory=list)
    groups: list[MediaPlayerEntity] = field(default_factory=list)
