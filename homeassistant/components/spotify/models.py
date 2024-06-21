"""Models for use in Spotify integration."""

from dataclasses import dataclass
from typing import Any

from spotipy import Spotify

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class HomeAssistantSpotifyData:
    """Spotify data stored in the Home Assistant data object."""

    client: Spotify
    current_user: dict[str, Any]
    devices: DataUpdateCoordinator[list[dict[str, Any]]]
    session: OAuth2Session
