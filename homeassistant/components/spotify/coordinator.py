"""Coordinator for Spotify."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from spotipy import Spotify, SpotifyException

from homeassistant.components.media_player import MediaType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class SpotifyCoordinatorData:
    """Class to hold Spotify data."""

    current_playback: dict[str, Any]
    position_updated_at: datetime | None
    playlist: dict[str, Any] | None


# This is a minimal representation of the DJ playlist that Spotify now offers
# The DJ is not fully integrated with the playlist API, so needs to have the
# playlist response mocked in order to maintain functionality
SPOTIFY_DJ_PLAYLIST = {"uri": "spotify:playlist:37i9dQZF1EYkqdzj48dyYq", "name": "DJ"}


class SpotifyCoordinator(DataUpdateCoordinator[SpotifyCoordinatorData]):
    """Class to manage fetching Spotify data."""

    current_user: dict[str, Any]

    def __init__(
        self, hass: HomeAssistant, client: Spotify, session: OAuth2Session
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client
        self._playlist: dict[str, Any] | None = None
        self.session = session

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            self.current_user = await self.hass.async_add_executor_job(self.client.me)
        except SpotifyException as err:
            raise UpdateFailed("Error communicating with Spotify API") from err
        if not self.current_user:
            raise UpdateFailed("Could not retrieve user")

    async def _async_update_data(self) -> SpotifyCoordinatorData:
        if not self.session.valid_token:
            await self.session.async_ensure_token_valid()
            await self.hass.async_add_executor_job(
                self.client.set_auth, self.session.token["access_token"]
            )
        return await self.hass.async_add_executor_job(self._sync_update_data)

    def _sync_update_data(self) -> SpotifyCoordinatorData:
        current = self.client.current_playback(additional_types=[MediaType.EPISODE])
        currently_playing = current or {}
        # Record the last updated time, because Spotify's timestamp property is unreliable
        # and doesn't actually return the fetch time as is mentioned in the API description
        position_updated_at = dt_util.utcnow() if current is not None else None

        context = currently_playing.get("context") or {}

        # For some users in some cases, the uri is formed like
        # "spotify:user:{name}:playlist:{id}" and spotipy wants
        # the type to be playlist.
        uri = context.get("uri")
        if uri is not None:
            parts = uri.split(":")
            if len(parts) == 5 and parts[1] == "user" and parts[3] == "playlist":
                uri = ":".join([parts[0], parts[3], parts[4]])

        if context and (self._playlist is None or self._playlist["uri"] != uri):
            self._playlist = None
            if context["type"] == MediaType.PLAYLIST:
                # The Spotify API does not currently support doing a lookup for
                # the DJ playlist,so just use the minimal mock playlist object
                if uri == SPOTIFY_DJ_PLAYLIST["uri"]:
                    self._playlist = SPOTIFY_DJ_PLAYLIST
                else:
                    # Make sure any playlist lookups don't break the current
                    # playback state update
                    try:
                        self._playlist = self.client.playlist(uri)
                    except SpotifyException:
                        _LOGGER.debug(
                            "Unable to load spotify playlist '%s'. "
                            "Continuing without playlist data",
                            uri,
                        )
                        self._playlist = None
        return SpotifyCoordinatorData(
            current_playback=currently_playing,
            position_updated_at=position_updated_at,
            playlist=self._playlist,
        )
