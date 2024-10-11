"""Coordinator for Spotify."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from spotifyaio import (
    PlaybackState,
    Playlist,
    SpotifyClient,
    SpotifyConnectionError,
    UserProfile,
)

from homeassistant.components.media_player import MediaType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class SpotifyCoordinatorData:
    """Class to hold Spotify data."""

    current_playback: PlaybackState | None
    position_updated_at: datetime | None
    playlist: Playlist | None
    dj_playlist: bool = False


# This is a minimal representation of the DJ playlist that Spotify now offers
# The DJ is not fully integrated with the playlist API, so we need to guard
# against trying to fetch it as a regular playlist
SPOTIFY_DJ_PLAYLIST_URI = "spotify:playlist:37i9dQZF1EYkqdzj48dyYq"


class SpotifyCoordinator(DataUpdateCoordinator[SpotifyCoordinatorData]):
    """Class to manage fetching Spotify data."""

    current_user: UserProfile

    def __init__(self, hass: HomeAssistant, client: SpotifyClient) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client
        self._playlist: Playlist | None = None

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            self.current_user = await self.client.get_current_user()
        except SpotifyConnectionError as err:
            raise UpdateFailed("Error communicating with Spotify API") from err

    async def _async_update_data(self) -> SpotifyCoordinatorData:
        current = await self.client.get_playback()
        if not current:
            return SpotifyCoordinatorData(
                current_playback=None, position_updated_at=None, playlist=None
            )
        # Record the last updated time, because Spotify's timestamp property is unreliable
        # and doesn't actually return the fetch time as is mentioned in the API description
        position_updated_at = dt_util.utcnow()

        dj_playlist = False
        if (context := current.context) is not None:
            if self._playlist is None or self._playlist.uri != context.uri:
                self._playlist = None
                if context.uri == SPOTIFY_DJ_PLAYLIST_URI:
                    dj_playlist = True
                elif context.context_type == MediaType.PLAYLIST:
                    # Make sure any playlist lookups don't break the current
                    # playback state update
                    try:
                        self._playlist = await self.client.get_playlist(context.uri)
                    except SpotifyConnectionError:
                        _LOGGER.debug(
                            "Unable to load spotify playlist '%s'. "
                            "Continuing without playlist data",
                            context.uri,
                        )
                        self._playlist = None
        return SpotifyCoordinatorData(
            current_playback=current,
            position_updated_at=position_updated_at,
            playlist=self._playlist,
            dj_playlist=dj_playlist,
        )
