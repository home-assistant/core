"""Support for interacting with Spotify Connect."""
from __future__ import annotations

from asyncio import run_coroutine_threadsafe
import datetime as dt
from datetime import timedelta
import logging
from typing import Any

import requests
from spotipy import Spotify, SpotifyException
from yarl import URL

from homeassistant.components.media_player import BrowseMedia, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp

from .browse_media import async_browse_media_internal
from .const import (
    DATA_SPOTIFY_CLIENT,
    DATA_SPOTIFY_ME,
    DATA_SPOTIFY_SESSION,
    DOMAIN,
    MEDIA_PLAYER_PREFIX,
    PLAYABLE_MEDIA_TYPES,
    SPOTIFY_SCOPES,
)
from .util import fetch_image_url

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

SUPPORT_SPOTIFY = (
    SUPPORT_BROWSE_MEDIA
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_REPEAT_SET
    | SUPPORT_SEEK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_VOLUME_SET
)

REPEAT_MODE_MAPPING_TO_HA = {
    "context": REPEAT_MODE_ALL,
    "off": REPEAT_MODE_OFF,
    "track": REPEAT_MODE_ONE,
}

REPEAT_MODE_MAPPING_TO_SPOTIFY = {
    value: key for key, value in REPEAT_MODE_MAPPING_TO_HA.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spotify based on a config entry."""
    spotify = SpotifyMediaPlayer(
        hass.data[DOMAIN][entry.entry_id],
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
        # pylint: disable=protected-access
        try:
            result = func(self, *args, **kwargs)
            self._attr_available = True
            return result
        except requests.RequestException:
            self._attr_available = False
        except SpotifyException as exc:
            self._attr_available = False
            if exc.reason == "NO_ACTIVE_DEVICE":
                raise HomeAssistantError("No active playback device found") from None

    return wrapper


class SpotifyMediaPlayer(MediaPlayerEntity):
    """Representation of a Spotify controller."""

    _attr_icon = "mdi:spotify"
    _attr_media_content_type = MEDIA_TYPE_MUSIC
    _attr_media_image_remotely_accessible = False

    def __init__(
        self,
        spotify_data,
        user_id: str,
        name: str,
    ) -> None:
        """Initialize."""
        self._id = user_id
        self._spotify_data = spotify_data
        self._name = f"Spotify {name}"
        self._scope_ok = set(self._session.token["scope"].split(" ")).issuperset(
            SPOTIFY_SCOPES
        )

        self._currently_playing: dict | None = {}
        self._devices: list[dict] | None = []
        self._playlist: dict | None = None

        self._attr_name = self._name
        self._attr_unique_id = user_id

    @property
    def _me(self) -> dict[str, Any]:
        """Return spotify user info."""
        return self._spotify_data[DATA_SPOTIFY_ME]

    @property
    def _session(self) -> OAuth2Session:
        """Return spotify session."""
        return self._spotify_data[DATA_SPOTIFY_SESSION]

    @property
    def _spotify(self) -> Spotify:
        """Return spotify API."""
        return self._spotify_data[DATA_SPOTIFY_CLIENT]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        model = "Spotify Free"
        if self._me is not None:
            product = self._me["product"]
            model = f"Spotify {product}"

        return DeviceInfo(
            identifiers={(DOMAIN, self._id)},
            manufacturer="Spotify AB",
            model=model,
            name=self._name,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://open.spotify.com",
        )

    @property
    def state(self) -> str | None:
        """Return the playback state."""
        if not self._currently_playing:
            return STATE_IDLE
        if self._currently_playing["is_playing"]:
            return STATE_PLAYING
        return STATE_PAUSED

    @property
    def volume_level(self) -> float | None:
        """Return the device volume."""
        if not self._currently_playing:
            return None
        return self._currently_playing.get("device", {}).get("volume_percent", 0) / 100

    @property
    def media_content_id(self) -> str | None:
        """Return the media URL."""
        if not self._currently_playing:
            return None
        item = self._currently_playing.get("item") or {}
        return item.get("uri")

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if (
            self._currently_playing is None
            or self._currently_playing.get("item") is None
        ):
            return None
        return self._currently_playing["item"]["duration_ms"] / 1000

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if not self._currently_playing:
            return None
        return self._currently_playing["progress_ms"] / 1000

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid."""
        if not self._currently_playing:
            return None
        return utc_from_timestamp(self._currently_playing["timestamp"] / 1000)

    @property
    def media_image_url(self) -> str | None:
        """Return the media image URL."""
        if (
            not self._currently_playing
            or self._currently_playing.get("item") is None
            or not self._currently_playing["item"]["album"]["images"]
        ):
            return None
        return fetch_image_url(self._currently_playing["item"]["album"])

    @property
    def media_title(self) -> str | None:
        """Return the media title."""
        if not self._currently_playing:
            return None
        item = self._currently_playing.get("item") or {}
        return item.get("name")

    @property
    def media_artist(self) -> str | None:
        """Return the media artist."""
        if not self._currently_playing or self._currently_playing.get("item") is None:
            return None
        return ", ".join(
            artist["name"] for artist in self._currently_playing["item"]["artists"]
        )

    @property
    def media_album_name(self) -> str | None:
        """Return the media album."""
        if not self._currently_playing or self._currently_playing.get("item") is None:
            return None
        return self._currently_playing["item"]["album"]["name"]

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        if not self._currently_playing:
            return None
        item = self._currently_playing.get("item") or {}
        return item.get("track_number")

    @property
    def media_playlist(self):
        """Title of Playlist currently playing."""
        if self._playlist is None:
            return None
        return self._playlist["name"]

    @property
    def source(self) -> str | None:
        """Return the current playback device."""
        if not self._currently_playing:
            return None
        return self._currently_playing.get("device", {}).get("name")

    @property
    def source_list(self) -> list[str] | None:
        """Return a list of source devices."""
        if not self._devices:
            return None
        return [device["name"] for device in self._devices]

    @property
    def shuffle(self) -> bool | None:
        """Shuffling state."""
        if not self._currently_playing:
            return None
        return self._currently_playing.get("shuffle_state")

    @property
    def repeat(self) -> str | None:
        """Return current repeat mode."""
        if (
            not self._currently_playing
            or (repeat_state := self._currently_playing.get("repeat_state")) is None
        ):
            return None
        return REPEAT_MODE_MAPPING_TO_HA.get(repeat_state)

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
        if media_type.startswith(MEDIA_PLAYER_PREFIX):
            media_type = media_type[len(MEDIA_PLAYER_PREFIX) :]

        kwargs = {}

        # Spotify can't handle URI's with query strings or anchors
        # Yet, they do generate those types of URI in their official clients.
        media_id = str(URL(media_id).with_query(None).with_fragment(None))

        if media_type in (MEDIA_TYPE_TRACK, MEDIA_TYPE_EPISODE, MEDIA_TYPE_MUSIC):
            kwargs["uris"] = [media_id]
        elif media_type in PLAYABLE_MEDIA_TYPES:
            kwargs["context_uri"] = media_id
        else:
            _LOGGER.error("Media type %s is not supported", media_type)
            return

        if (
            self._currently_playing
            and not self._currently_playing.get("device")
            and self._devices
        ):
            kwargs["device_id"] = self._devices[0].get("id")

        self._spotify.start_playback(**kwargs)

    @spotify_exception_handler
    def select_source(self, source: str) -> None:
        """Select playback device."""
        if not self._devices:
            return

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
    def set_repeat(self, repeat: str) -> None:
        """Set repeat mode."""
        if repeat not in REPEAT_MODE_MAPPING_TO_SPOTIFY:
            raise ValueError(f"Unsupported repeat mode: {repeat}")
        self._spotify.repeat(REPEAT_MODE_MAPPING_TO_SPOTIFY[repeat])

    @spotify_exception_handler
    def update(self) -> None:
        """Update state and attributes."""
        if not self.enabled:
            return

        if not self._session.valid_token or self._spotify is None:
            run_coroutine_threadsafe(
                self._session.async_ensure_token_valid(), self.hass.loop
            ).result()
            self._spotify_data[DATA_SPOTIFY_CLIENT] = Spotify(
                auth=self._session.token["access_token"]
            )

        current = self._spotify.current_playback()
        self._currently_playing = current or {}

        self._playlist = None
        context = self._currently_playing.get("context")
        if context is not None and context["type"] == MEDIA_TYPE_PLAYLIST:
            self._playlist = self._spotify.playlist(current["context"]["uri"])

        devices = self._spotify.devices() or {}
        self._devices = devices.get("devices", [])

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""

        if not self._scope_ok:
            _LOGGER.debug(
                "Spotify scopes are not set correctly, this can impact features such as media browsing"
            )
            raise NotImplementedError

        return await async_browse_media_internal(
            self.hass,
            self._spotify,
            self._session,
            self._me,
            media_content_type,
            media_content_id,
        )
