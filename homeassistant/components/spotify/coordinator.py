"""Coordinator for Spotify."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from spotifyaio import (
    ContextType,
    Device,
    PlaybackState,
    Playlist,
    SpotifyClient,
    SpotifyConnectionError,
    SpotifyForbiddenError,
    SpotifyNotFoundError,
    UserProfile,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


type SpotifyConfigEntry = ConfigEntry[SpotifyData]


@dataclass
class SpotifyData:
    """Class to hold Spotify data."""

    coordinator: SpotifyCoordinator
    session: OAuth2Session
    devices: SpotifyDeviceCoordinator


UPDATE_INTERVAL = timedelta(seconds=30)

FREE_API_BLOGPOST = (
    "https://developer.spotify.com/blog/"
    "2026-02-06-update-on-developer-access-and-platform-security"
)


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
    config_entry: SpotifyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SpotifyConfigEntry,
        client: SpotifyClient,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self._playlist: Playlist | None = None
        self._checked_playlist_id: str | None = None

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            self.current_user = await self.client.get_current_user()
        except SpotifyForbiddenError as err:
            async_create_issue(
                self.hass,
                DOMAIN,
                f"user_not_premium_{self.config_entry.unique_id}",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.ERROR,
                translation_key="user_not_premium",
                translation_placeholders={"entry_title": self.config_entry.title},
                learn_more_url=FREE_API_BLOGPOST,
            )
            raise ConfigEntryError("User is not subscribed to Spotify") from err
        except SpotifyConnectionError as err:
            raise UpdateFailed("Error communicating with Spotify API") from err

    async def _async_update_data(self) -> SpotifyCoordinatorData:
        self.update_interval = UPDATE_INTERVAL
        try:
            current = await self.client.get_playback()
        except SpotifyConnectionError as err:
            raise UpdateFailed("Error communicating with Spotify API") from err
        if not current:
            return SpotifyCoordinatorData(
                current_playback=None,
                position_updated_at=None,
                playlist=None,
            )
        # Record the last updated time, because Spotify's timestamp property is unreliable
        # and doesn't actually return the fetch time as is mentioned in the API description
        position_updated_at = dt_util.utcnow()

        dj_playlist = False
        if (context := current.context) is not None:
            dj_playlist = context.uri == SPOTIFY_DJ_PLAYLIST_URI
            if not (
                context.uri
                in (
                    self._checked_playlist_id,
                    SPOTIFY_DJ_PLAYLIST_URI,
                )
                or (self._playlist is None and context.uri == self._checked_playlist_id)
            ):
                self._checked_playlist_id = context.uri
                self._playlist = None
                if context.context_type == ContextType.PLAYLIST:
                    # Make sure any playlist lookups don't break the current
                    # playback state update
                    try:
                        self._playlist = await self.client.get_playlist(context.uri)
                    except SpotifyNotFoundError:
                        _LOGGER.debug(
                            "Spotify playlist '%s' not found. "
                            "Most likely a Spotify-created playlist",
                            context.uri,
                        )
                        self._playlist = None
                    except SpotifyConnectionError:
                        _LOGGER.debug(
                            "Unable to load spotify playlist '%s'. "
                            "Continuing without playlist data",
                            context.uri,
                        )
                        self._playlist = None
                        self._checked_playlist_id = None
        if current.is_playing and current.progress_ms is not None:
            assert current.item is not None
            time_left = timedelta(
                milliseconds=current.item.duration_ms - current.progress_ms
            )
            if time_left < UPDATE_INTERVAL:
                self.update_interval = time_left + timedelta(seconds=1)
        return SpotifyCoordinatorData(
            current_playback=current,
            position_updated_at=position_updated_at,
            playlist=self._playlist,
            dj_playlist=dj_playlist,
        )


class SpotifyDeviceCoordinator(DataUpdateCoordinator[list[Device]]):
    """Class to manage fetching Spotify data."""

    config_entry: SpotifyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SpotifyConfigEntry,
        client: SpotifyClient,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{config_entry.title} Devices",
            update_interval=timedelta(minutes=5),
        )
        self._client = client

    async def _async_update_data(self) -> list[Device]:
        try:
            return await self._client.get_devices()
        except SpotifyConnectionError as err:
            raise UpdateFailed from err
