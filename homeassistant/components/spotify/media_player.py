"""Support for interacting with Spotify Connect."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import datetime as dt
import logging
from typing import TYPE_CHECKING, Any, Concatenate

from spotifyaio import (
    Device,
    Episode,
    Item,
    ItemType,
    PlaybackState,
    ProductType,
    RepeatMode as SpotifyRepeatMode,
    Track,
)
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .browse_media import async_browse_media_internal
from .const import MEDIA_PLAYER_PREFIX, PLAYABLE_MEDIA_TYPES
from .coordinator import SpotifyConfigEntry, SpotifyCoordinator
from .entity import SpotifyEntity

_LOGGER = logging.getLogger(__name__)

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
    SpotifyRepeatMode.CONTEXT: RepeatMode.ALL,
    SpotifyRepeatMode.OFF: RepeatMode.OFF,
    SpotifyRepeatMode.TRACK: RepeatMode.ONE,
}

REPEAT_MODE_MAPPING_TO_SPOTIFY = {
    value: key for key, value in REPEAT_MODE_MAPPING_TO_HA.items()
}
AFTER_REQUEST_SLEEP = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpotifyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spotify based on a config entry."""
    data = entry.runtime_data
    assert entry.unique_id is not None
    spotify = SpotifyMediaPlayer(
        data.coordinator,
        data.devices,
    )
    async_add_entities([spotify])


def ensure_item[_R](
    func: Callable[[SpotifyMediaPlayer, Item], _R],
) -> Callable[[SpotifyMediaPlayer], _R | None]:
    """Ensure that the currently playing item is available."""

    def wrapper(self: SpotifyMediaPlayer) -> _R | None:
        if not self.currently_playing or not self.currently_playing.item:
            return None
        return func(self, self.currently_playing.item)

    return wrapper


def async_refresh_after[_T: SpotifyEntity, **_P](
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to yield and refresh after."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        await func(self, *args, **kwargs)
        await asyncio.sleep(AFTER_REQUEST_SLEEP)
        await self.coordinator.async_refresh()

    return _async_wrap


class SpotifyMediaPlayer(SpotifyEntity, MediaPlayerEntity):
    """Representation of a Spotify controller."""

    _attr_media_image_remotely_accessible = False
    _attr_name = None
    _attr_translation_key = "spotify"

    def __init__(
        self,
        coordinator: SpotifyCoordinator,
        device_coordinator: DataUpdateCoordinator[list[Device]],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.devices = device_coordinator
        self._attr_unique_id = coordinator.current_user.user_id

    @property
    def currently_playing(self) -> PlaybackState | None:
        """Return the current playback."""
        return self.coordinator.data.current_playback

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the supported features."""
        if self.coordinator.current_user.product != ProductType.PREMIUM:
            return MediaPlayerEntityFeature(0)
        if not self.currently_playing or self.currently_playing.device.is_restricted:
            return MediaPlayerEntityFeature.SELECT_SOURCE
        return SUPPORT_SPOTIFY

    @property
    def state(self) -> MediaPlayerState:
        """Return the playback state."""
        if not self.currently_playing:
            return MediaPlayerState.IDLE
        if self.currently_playing.is_playing:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.PAUSED

    @property
    def volume_level(self) -> float | None:
        """Return the device volume."""
        if not self.currently_playing:
            return None
        return self.currently_playing.device.volume_percent / 100

    @property
    @ensure_item
    def media_content_id(self, item: Item) -> str:  # noqa: PLR0206
        """Return the media URL."""
        return item.uri

    @property
    @ensure_item
    def media_content_type(self, item: Item) -> str:  # noqa: PLR0206
        """Return the media type."""
        return MediaType.PODCAST if item.type == ItemType.EPISODE else MediaType.MUSIC

    @property
    @ensure_item
    def media_duration(self, item: Item) -> int:  # noqa: PLR0206
        """Duration of current playing media in seconds."""
        return round(item.duration_ms / 1000)

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if not self.currently_playing or self.currently_playing.progress_ms is None:
            return None
        return round(self.currently_playing.progress_ms / 1000)

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid."""
        if not self.currently_playing:
            return None
        return self.coordinator.data.position_updated_at

    @property
    @ensure_item
    def media_image_url(self, item: Item) -> str | None:  # noqa: PLR0206
        """Return the media image URL."""
        if item.type == ItemType.EPISODE:
            if TYPE_CHECKING:
                assert isinstance(item, Episode)
            if item.images:
                return item.images[0].url
            if item.show and item.show.images:
                return item.show.images[0].url
            return None
        if TYPE_CHECKING:
            assert isinstance(item, Track)
        if not item.album.images:
            return None
        return item.album.images[0].url

    @property
    @ensure_item
    def media_title(self, item: Item) -> str:  # noqa: PLR0206
        """Return the media title."""
        return item.name

    @property
    @ensure_item
    def media_artist(self, item: Item) -> str:  # noqa: PLR0206
        """Return the media artist."""
        if item.type == ItemType.EPISODE:
            if TYPE_CHECKING:
                assert isinstance(item, Episode)
            return item.show.publisher

        if TYPE_CHECKING:
            assert isinstance(item, Track)
        return ", ".join(artist.name for artist in item.artists)

    @property
    @ensure_item
    def media_album_name(self, item: Item) -> str:  # noqa: PLR0206
        """Return the media album."""
        if item.type == ItemType.EPISODE:
            if TYPE_CHECKING:
                assert isinstance(item, Episode)
            return item.show.name

        if TYPE_CHECKING:
            assert isinstance(item, Track)
        return item.album.name

    @property
    @ensure_item
    def media_track(self, item: Item) -> int | None:  # noqa: PLR0206
        """Track number of current playing media, music track only."""
        if item.type == ItemType.EPISODE:
            return None
        if TYPE_CHECKING:
            assert isinstance(item, Track)
        return item.track_number

    @property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        if self.coordinator.data.dj_playlist:
            return "DJ"
        if self.coordinator.data.playlist is None:
            return None
        return self.coordinator.data.playlist.name

    @property
    def source(self) -> str | None:
        """Return the current playback device."""
        if not self.currently_playing:
            return None
        return self.currently_playing.device.name

    @property
    def source_list(self) -> list[str] | None:
        """Return a list of source devices."""
        return [device.name for device in self.devices.data]

    @property
    def shuffle(self) -> bool | None:
        """Shuffling state."""
        if not self.currently_playing:
            return None
        return self.currently_playing.shuffle

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if not self.currently_playing:
            return None
        return REPEAT_MODE_MAPPING_TO_HA.get(self.currently_playing.repeat_mode)

    @async_refresh_after
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        await self.coordinator.client.set_volume(int(volume * 100))

    @async_refresh_after
    async def async_media_play(self) -> None:
        """Start or resume playback."""
        await self.coordinator.client.start_playback()

    @async_refresh_after
    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self.coordinator.client.pause_playback()

    @async_refresh_after
    async def async_media_previous_track(self) -> None:
        """Skip to previous track."""
        await self.coordinator.client.previous_track()

    @async_refresh_after
    async def async_media_next_track(self) -> None:
        """Skip to next track."""
        await self.coordinator.client.next_track()

    @async_refresh_after
    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self.coordinator.client.seek_track(int(position * 1000))

    @async_refresh_after
    async def async_play_media(
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

        if not self.currently_playing and self.devices.data:
            kwargs["device_id"] = self.devices.data[0].device_id

        if enqueue == MediaPlayerEnqueue.ADD:
            if media_type not in {
                MediaType.TRACK,
                MediaType.EPISODE,
                MediaType.MUSIC,
            }:
                raise ValueError(
                    f"Media type {media_type} is not supported when enqueue is ADD"
                )
            await self.coordinator.client.add_to_queue(
                media_id, kwargs.get("device_id")
            )
            return

        await self.coordinator.client.start_playback(**kwargs)

    @async_refresh_after
    async def async_select_source(self, source: str) -> None:
        """Select playback device."""
        for device in self.devices.data:
            if device.name == source:
                await self.coordinator.client.transfer_playback(device.device_id)
                return

    @async_refresh_after
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/Disable shuffle mode."""
        await self.coordinator.client.set_shuffle(state=shuffle)

    @async_refresh_after
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        if repeat not in REPEAT_MODE_MAPPING_TO_SPOTIFY:
            raise ValueError(f"Unsupported repeat mode: {repeat}")
        await self.coordinator.client.set_repeat(REPEAT_MODE_MAPPING_TO_SPOTIFY[repeat])

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""

        return await async_browse_media_internal(
            self.hass,
            self.coordinator.client,
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
            self.devices.async_add_listener(self._handle_devices_update)
        )
