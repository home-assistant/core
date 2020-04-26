"""Support for interacting with Spotify Connect."""
from asyncio import run_coroutine_threadsafe
import datetime as dt
from datetime import timedelta
import logging
from typing import Any, Callable, Dict, List, Optional

from aiohttp import ClientError
from spotipy import Spotify, SpotifyException
from yarl import URL

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utc_from_timestamp

from .const import DATA_SPOTIFY_CLIENT, DATA_SPOTIFY_ME, DATA_SPOTIFY_SESSION, DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:spotify"

SCAN_INTERVAL = timedelta(seconds=30)

SUPPORT_SPOTIFY = (
    SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SEEK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_VOLUME_SET
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Spotify based on a config entry."""
    spotify = SpotifyMediaPlayer(
        hass.data[DOMAIN][entry.entry_id][DATA_SPOTIFY_SESSION],
        hass.data[DOMAIN][entry.entry_id][DATA_SPOTIFY_CLIENT],
        hass.data[DOMAIN][entry.entry_id][DATA_SPOTIFY_ME],
        entry.data[CONF_ID],
        entry.data[CONF_NAME],
    )
    async_add_entities([spotify], True)


def spotify_exception_handler(func):
    """Decorate Spotify calls to handle Spotify exception.

    A decorator that wraps the passed in function, catches Spotify errors,
    aiohttp exceptions and handles the availability of the media player.
    """

    def wrapper(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)
            self.player_available = True
            return result
        except (SpotifyException, ClientError):
            self.player_available = False

    return wrapper


class SpotifyMediaPlayer(MediaPlayerEntity):
    """Representation of a Spotify controller."""

    def __init__(
        self,
        session: OAuth2Session,
        spotify: Spotify,
        me: dict,
        user_id: str,
        name: str,
    ):
        """Initialize."""
        self._id = user_id
        self._me = me
        self._name = f"Spotify {name}"
        self._session = session
        self._spotify = spotify

        self._currently_playing: Optional[dict] = {}
        self._devices: Optional[List[dict]] = []
        self._playlist: Optional[dict] = None
        self._spotify: Spotify = None

        self.player_available = False

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon."""
        return ICON

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.player_available

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return self._id

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        if self._me is not None:
            model = self._me["product"]

        return {
            "identifiers": {(DOMAIN, self._id)},
            "manufacturer": "Spotify AB",
            "model": f"Spotify {model}".rstrip(),
            "name": self._name,
        }

    @property
    def state(self) -> Optional[str]:
        """Return the playback state."""
        if not self._currently_playing:
            return STATE_IDLE
        if self._currently_playing["is_playing"]:
            return STATE_PLAYING
        return STATE_PAUSED

    @property
    def volume_level(self) -> Optional[float]:
        """Return the device volume."""
        return self._currently_playing.get("device", {}).get("volume_percent", 0) / 100

    @property
    def media_content_id(self) -> Optional[str]:
        """Return the media URL."""
        item = self._currently_playing.get("item") or {}
        return item.get("name")

    @property
    def media_content_type(self) -> Optional[str]:
        """Return the media type."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self) -> Optional[int]:
        """Duration of current playing media in seconds."""
        if self._currently_playing.get("item") is None:
            return None
        return self._currently_playing["item"]["duration_ms"] / 1000

    @property
    def media_position(self) -> Optional[str]:
        """Position of current playing media in seconds."""
        if not self._currently_playing:
            return None
        return self._currently_playing["progress_ms"] / 1000

    @property
    def media_position_updated_at(self) -> Optional[dt.datetime]:
        """When was the position of the current playing media valid."""
        if not self._currently_playing:
            return None
        return utc_from_timestamp(self._currently_playing["timestamp"] / 1000)

    @property
    def media_image_url(self) -> Optional[str]:
        """Return the media image URL."""
        if (
            self._currently_playing.get("item") is None
            or not self._currently_playing["item"]["album"]["images"]
        ):
            return None
        return self._currently_playing["item"]["album"]["images"][0]["url"]

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return False

    @property
    def media_title(self) -> Optional[str]:
        """Return the media title."""
        item = self._currently_playing.get("item") or {}
        return item.get("name")

    @property
    def media_artist(self) -> Optional[str]:
        """Return the media artist."""
        if self._currently_playing.get("item") is None:
            return None
        return ", ".join(
            [artist["name"] for artist in self._currently_playing["item"]["artists"]]
        )

    @property
    def media_album_name(self) -> Optional[str]:
        """Return the media album."""
        if self._currently_playing.get("item") is None:
            return None
        return self._currently_playing["item"]["album"]["name"]

    @property
    def media_track(self) -> Optional[int]:
        """Track number of current playing media, music track only."""
        item = self._currently_playing.get("item") or {}
        return item.get("track_number")

    @property
    def media_playlist(self):
        """Title of Playlist currently playing."""
        if self._playlist is None:
            return None
        return self._playlist["name"]

    @property
    def source(self) -> Optional[str]:
        """Return the current playback device."""
        return self._currently_playing.get("device", {}).get("name")

    @property
    def source_list(self) -> Optional[List[str]]:
        """Return a list of source devices."""
        if not self._devices:
            return None
        return [device["name"] for device in self._devices]

    @property
    def shuffle(self) -> bool:
        """Shuffling state."""
        return bool(self._currently_playing.get("shuffle_state"))

    @property
    def supported_features(self) -> int:
        """Return the media player features that are supported."""
        if self._me["product"] != "premium":
            return 0
        return SUPPORT_SPOTIFY

    @spotify_exception_handler
    def set_volume_level(self, volume: int) -> None:
        """Set the volume level."""
        self._spotify.volume(int(volume * 100))

    @spotify_exception_handler
    def media_play(self) -> None:
        """Start or resume playback."""
        self._spotify.start_playback()

    @spotify_exception_handler
    def media_pause(self) -> None:
        """Pause playback."""
        self._spotify.pause_playback()

    @spotify_exception_handler
    def media_previous_track(self) -> None:
        """Skip to previous track."""
        self._spotify.previous_track()

    @spotify_exception_handler
    def media_next_track(self) -> None:
        """Skip to next track."""
        self._spotify.next_track()

    @spotify_exception_handler
    def media_seek(self, position):
        """Send seek command."""
        self._spotify.seek_track(int(position * 1000))

    @spotify_exception_handler
    def play_media(self, media_type: str, media_id: str, **kwargs) -> None:
        """Play media."""
        kwargs = {}

        # Spotify can't handle URI's with query strings or anchors
        # Yet, they do generate those types of URI in their official clients.
        media_id = str(URL(media_id).with_query(None).with_fragment(None))

        if media_type == MEDIA_TYPE_MUSIC:
            kwargs["uris"] = [media_id]
        elif media_type == MEDIA_TYPE_PLAYLIST:
            kwargs["context_uri"] = media_id
        else:
            _LOGGER.error("Media type %s is not supported", media_type)
            return

        self._spotify.start_playback(**kwargs)

    @spotify_exception_handler
    def select_source(self, source: str) -> None:
        """Select playback device."""
        for device in self._devices:
            if device["name"] == source:
                self._spotify.transfer_playback(
                    device["id"], self.state == STATE_PLAYING
                )
                return

    @spotify_exception_handler
    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/Disable shuffle mode."""
        self._spotify.shuffle(shuffle)

    @spotify_exception_handler
    def update(self) -> None:
        """Update state and attributes."""
        if not self.enabled:
            return

        if not self._session.valid_token or self._spotify is None:
            run_coroutine_threadsafe(
                self._session.async_ensure_token_valid(), self.hass.loop
            ).result()
            self._spotify = Spotify(auth=self._session.token["access_token"])

        current = self._spotify.current_playback()
        self._currently_playing = current or {}

        self._playlist = None
        context = self._currently_playing.get("context")
        if context is not None and context["type"] == MEDIA_TYPE_PLAYLIST:
            self._playlist = self._spotify.playlist(current["context"]["uri"])

        devices = self._spotify.devices() or {}
        self._devices = devices.get("devices", [])
