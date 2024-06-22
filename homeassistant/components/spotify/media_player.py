"""Support for interacting with Spotify Connect."""

from __future__ import annotations

from asyncio import run_coroutine_threadsafe
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any, Concatenate

import requests
from spotipy import SpotifyException
from yarl import URL

from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    BrowseMedia,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from . import SpotifyConfigEntry
from .browse_media import async_browse_media_internal
from .const import DOMAIN, MEDIA_PLAYER_PREFIX, PLAYABLE_MEDIA_TYPES, SPOTIFY_SCOPES
from .models import HomeAssistantSpotifyData
from .util import fetch_image_url

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

SUPPORT_SPOTIFY = (
    MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.VOLUME_SET
)

REPEAT_MODE_MAPPING_TO_HA = {
    "context": RepeatMode.ALL,
    "off": RepeatMode.OFF,
    "track": RepeatMode.ONE,
}

REPEAT_MODE_MAPPING_TO_SPOTIFY = {
    value: key for key, value in REPEAT_MODE_MAPPING_TO_HA.items()
}

# This is a minimal representation of the DJ playlist that Spotify now offers
# The DJ is not fully integrated with the playlist API, so needs to have the playlist response mocked in order to maintain functionality
SPOTIFY_DJ_PLAYLIST = {"uri": "spotify:playlist:37i9dQZF1EYkqdzj48dyYq", "name": "DJ"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpotifyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spotify based on a config entry."""
    spotify = SpotifyMediaPlayer(
        entry.runtime_data,
        entry.data[CONF_ID],
        entry.title,
    )
    async_add_entities([spotify], True)


def spotify_exception_handler[_SpotifyMediaPlayerT: SpotifyMediaPlayer, **_P, _R](
    func: Callable[Concatenate[_SpotifyMediaPlayerT, _P], _R],
) -> Callable[Concatenate[_SpotifyMediaPlayerT, _P], _R | None]:
    """Decorate Spotify calls to handle Spotify exception.

    A decorator that wraps the passed in function, catches Spotify errors,
    aiohttp exceptions and handles the availability of the media player.
    """

    def wrapper(
        self: _SpotifyMediaPlayerT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R | None:
        try:
            result = func(self, *args, **kwargs)
        except requests.RequestException:
            self._attr_available = False
            return None
        except SpotifyException as exc:
            self._attr_available = False
            if exc.reason == "NO_ACTIVE_DEVICE":
                raise HomeAssistantError("No active playback device found") from None
            raise HomeAssistantError(f"Spotify error: {exc.reason}") from exc
        self._attr_available = True
        return result

    return wrapper


class SpotifyMediaPlayer(MediaPlayerEntity):
    """Representation of a Spotify controller."""

    _attr_has_entity_name = True
    _attr_media_image_remotely_accessible = False
    _attr_name = None
    _attr_translation_key = "spotify"

    def __init__(
        self,
        data: HomeAssistantSpotifyData,
        user_id: str,
        name: str,
    ) -> None:
        """Initialize."""
        self._id = user_id
        self.data = data

        self._attr_unique_id = user_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
            manufacturer="Spotify AB",
            model=f"Spotify {data.current_user['product']}",
            name=f"Spotify {name}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://open.spotify.com",
        )

        self._scope_ok = set(data.session.token["scope"].split(" ")).issuperset(
            SPOTIFY_SCOPES
        )
        self._currently_playing: dict | None = {}
        self._playlist: dict | None = None
        self._restricted_device: bool = False

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the supported features."""
        if self.data.current_user["product"] != "premium":
            return MediaPlayerEntityFeature(0)
        if self._restricted_device or not self._currently_playing:
            return MediaPlayerEntityFeature.SELECT_SOURCE
        return SUPPORT_SPOTIFY

    @property
    def state(self) -> MediaPlayerState:
        """Return the playback state."""
        if not self._currently_playing:
            return MediaPlayerState.IDLE
        if self._currently_playing["is_playing"]:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.PAUSED

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
    def media_content_type(self) -> str | None:
        """Return the media type."""
        if not self._currently_playing:
            return None
        item = self._currently_playing.get("item") or {}
        is_episode = item.get("type") == MediaType.EPISODE
        return MediaType.PODCAST if is_episode else MediaType.MUSIC

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
        if (
            not self._currently_playing
            or self._currently_playing.get("progress_ms") is None
        ):
            return None
        return self._currently_playing["progress_ms"] / 1000

    @property
    def media_image_url(self) -> str | None:
        """Return the media image URL."""
        if not self._currently_playing or self._currently_playing.get("item") is None:
            return None

        item = self._currently_playing["item"]
        if item["type"] == MediaType.EPISODE:
            if item["images"]:
                return fetch_image_url(item)
            if item["show"]["images"]:
                return fetch_image_url(item["show"])
            return None

        if not item["album"]["images"]:
            return None
        return fetch_image_url(item["album"])

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

        item = self._currently_playing["item"]
        if item["type"] == MediaType.EPISODE:
            return item["show"]["publisher"]

        return ", ".join(artist["name"] for artist in item["artists"])

    @property
    def media_album_name(self) -> str | None:
        """Return the media album."""
        if not self._currently_playing or self._currently_playing.get("item") is None:
            return None

        item = self._currently_playing["item"]
        if item["type"] == MediaType.EPISODE:
            return item["show"]["name"]

        return item["album"]["name"]

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
        return [device["name"] for device in self.data.devices.data]

    @property
    def shuffle(self) -> bool | None:
        """Shuffling state."""
        if not self._currently_playing:
            return None
        return self._currently_playing.get("shuffle_state")

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if (
            not self._currently_playing
            or (repeat_state := self._currently_playing.get("repeat_state")) is None
        ):
            return None
        return REPEAT_MODE_MAPPING_TO_HA.get(repeat_state)

    @spotify_exception_handler
    def set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        self.data.client.volume(int(volume * 100))

    @spotify_exception_handler
    def media_play(self) -> None:
        """Start or resume playback."""
        self.data.client.start_playback()

    @spotify_exception_handler
    def media_pause(self) -> None:
        """Pause playback."""
        self.data.client.pause_playback()

    @spotify_exception_handler
    def media_previous_track(self) -> None:
        """Skip to previous track."""
        self.data.client.previous_track()

    @spotify_exception_handler
    def media_next_track(self) -> None:
        """Skip to next track."""
        self.data.client.next_track()

    @spotify_exception_handler
    def media_seek(self, position: float) -> None:
        """Send seek command."""
        self.data.client.seek_track(int(position * 1000))

    @spotify_exception_handler
    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media."""
        media_type = media_type.removeprefix(MEDIA_PLAYER_PREFIX)

        enqueue: MediaPlayerEnqueue = kwargs.get(
            ATTR_MEDIA_ENQUEUE, MediaPlayerEnqueue.REPLACE
        )

        kwargs = {}

        # Spotify can't handle URI's with query strings or anchors
        # Yet, they do generate those types of URI in their official clients.
        media_id = str(URL(media_id).with_query(None).with_fragment(None))

        if media_type in {MediaType.TRACK, MediaType.EPISODE, MediaType.MUSIC}:
            kwargs["uris"] = [media_id]
        elif media_type in PLAYABLE_MEDIA_TYPES:
            kwargs["context_uri"] = media_id
        else:
            _LOGGER.error("Media type %s is not supported", media_type)
            return

        if (
            self._currently_playing
            and not self._currently_playing.get("device")
            and self.data.devices.data
        ):
            kwargs["device_id"] = self.data.devices.data[0].get("id")

        if enqueue == MediaPlayerEnqueue.ADD:
            if media_type not in {
                MediaType.TRACK,
                MediaType.EPISODE,
                MediaType.MUSIC,
            }:
                raise ValueError(
                    f"Media type {media_type} is not supported when enqueue is ADD"
                )
            self.data.client.add_to_queue(media_id, kwargs.get("device_id"))
            return

        self.data.client.start_playback(**kwargs)

    @spotify_exception_handler
    def select_source(self, source: str) -> None:
        """Select playback device."""
        for device in self.data.devices.data:
            if device["name"] == source:
                self.data.client.transfer_playback(
                    device["id"], self.state == MediaPlayerState.PLAYING
                )
                return

    @spotify_exception_handler
    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/Disable shuffle mode."""
        self.data.client.shuffle(shuffle)

    @spotify_exception_handler
    def set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        if repeat not in REPEAT_MODE_MAPPING_TO_SPOTIFY:
            raise ValueError(f"Unsupported repeat mode: {repeat}")
        self.data.client.repeat(REPEAT_MODE_MAPPING_TO_SPOTIFY[repeat])

    @spotify_exception_handler
    def update(self) -> None:
        """Update state and attributes."""
        if not self.enabled:
            return

        if not self.data.session.valid_token or self.data.client is None:
            run_coroutine_threadsafe(
                self.data.session.async_ensure_token_valid(), self.hass.loop
            ).result()
            self.data.client.set_auth(auth=self.data.session.token["access_token"])

        current = self.data.client.current_playback(
            additional_types=[MediaType.EPISODE]
        )
        self._currently_playing = current or {}
        # Record the last updated time, because Spotify's timestamp property is unreliable
        # and doesn't actually return the fetch time as is mentioned in the API description
        self._attr_media_position_updated_at = utcnow() if current is not None else None

        context = self._currently_playing.get("context") or {}

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
                # The Spotify API does not currently support doing a lookup for the DJ playlist, so just use the minimal mock playlist object
                if uri == SPOTIFY_DJ_PLAYLIST["uri"]:
                    self._playlist = SPOTIFY_DJ_PLAYLIST
                else:
                    # Make sure any playlist lookups don't break the current playback state update
                    try:
                        self._playlist = self.data.client.playlist(uri)
                    except SpotifyException:
                        _LOGGER.debug(
                            "Unable to load spotify playlist '%s'. Continuing without playlist data",
                            uri,
                        )
                        self._playlist = None

        device = self._currently_playing.get("device")
        if device is not None:
            self._restricted_device = device["is_restricted"]

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""

        if not self._scope_ok:
            _LOGGER.debug(
                "Spotify scopes are not set correctly, this can impact features such as"
                " media browsing"
            )
            raise NotImplementedError

        return await async_browse_media_internal(
            self.hass,
            self.data.client,
            self.data.session,
            self.data.current_user,
            media_content_type,
            media_content_id,
        )

    @callback
    def _handle_devices_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.enabled:
            return
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.data.devices.async_add_listener(self._handle_devices_update)
        )
