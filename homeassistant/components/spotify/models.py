"""Models for use in Spotify integration."""

from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .coordinator import SpotifyCoordinator


@dataclass
class SpotifyData:
    """Class to hold Spotify data."""

    coordinator: SpotifyCoordinator
    session: OAuth2Session
    devices: DataUpdateCoordinator[list[dict[str, Any]]]
