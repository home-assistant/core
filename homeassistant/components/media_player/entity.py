"""Base entity for the Media player platform."""

import asyncio
import collections
from contextlib import suppress
import datetime as dt
import functools as ft
from functools import lru_cache
import hashlib
from http import HTTPStatus
import logging
import secrets
from typing import Any, Required, TypedDict, final, override
from urllib.parse import quote, urlparse

import aiohttp
from aiohttp.hdrs import CONTENT_ENCODING, CONTENT_LENGTH, CONTENT_TYPE
from propcache.api import cached_property
from yarl import URL

from homeassistant.const import EntityStateAttribute
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.network import get_url

from .browse_media import BrowseMedia, SearchMedia, SearchMediaQuery
from .const import (
    CACHE_CONTENT,
    CACHE_IMAGES,
    CACHE_LOCK,
    CACHE_MAXSIZE,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntityCapabilityAttribute,
    MediaPlayerEntityFeature,
    MediaPlayerEntityStateAttribute,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)

_LOGGER = logging.getLogger(__package__)


PROP_TO_ATTR = {
    "volume_level": MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL,
    "is_volume_muted": MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED,
    "media_content_id": MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID,
    "media_content_type": MediaPlayerEntityStateAttribute.MEDIA_CONTENT_TYPE,
    "media_duration": MediaPlayerEntityStateAttribute.MEDIA_DURATION,
    "media_position": MediaPlayerEntityStateAttribute.MEDIA_POSITION,
    "media_position_updated_at": MediaPlayerEntityStateAttribute.MEDIA_POSITION_UPDATED_AT,
    "media_title": MediaPlayerEntityStateAttribute.MEDIA_TITLE,
    "media_artist": MediaPlayerEntityStateAttribute.MEDIA_ARTIST,
    "media_album_name": MediaPlayerEntityStateAttribute.MEDIA_ALBUM_NAME,
    "media_album_artist": MediaPlayerEntityStateAttribute.MEDIA_ALBUM_ARTIST,
    "media_track": MediaPlayerEntityStateAttribute.MEDIA_TRACK,
    "media_series_title": MediaPlayerEntityStateAttribute.MEDIA_SERIES_TITLE,
    "media_season": MediaPlayerEntityStateAttribute.MEDIA_SEASON,
    "media_episode": MediaPlayerEntityStateAttribute.MEDIA_EPISODE,
    "media_channel": MediaPlayerEntityStateAttribute.MEDIA_CHANNEL,
    "media_playlist": MediaPlayerEntityStateAttribute.MEDIA_PLAYLIST,
    "app_id": MediaPlayerEntityStateAttribute.APP_ID,
    "app_name": MediaPlayerEntityStateAttribute.APP_NAME,
    "source": MediaPlayerEntityStateAttribute.INPUT_SOURCE,
    "sound_mode": MediaPlayerEntityStateAttribute.SOUND_MODE,
    "shuffle": MediaPlayerEntityStateAttribute.MEDIA_SHUFFLE,
    "repeat": MediaPlayerEntityStateAttribute.MEDIA_REPEAT,
}


class _CacheImage(TypedDict, total=False):
    """Class to hold a cached image."""

    lock: Required[asyncio.Lock]
    content: tuple[bytes | None, str | None]


class _ImageCache(TypedDict):
    """Class to hold a cached image."""

    images: collections.OrderedDict[str, _CacheImage]
    maxsize: int


_ENTITY_IMAGE_CACHE = _ImageCache(images=collections.OrderedDict(), maxsize=16)


class MediaPlayerEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes media player entities."""

    device_class: MediaPlayerDeviceClass | None = None
    volume_step: float | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
    "state",
    "volume_level",
    "volume_step",
    "is_volume_muted",
    "media_content_id",
    "media_content_type",
    "media_duration",
    "media_position",
    "media_position_updated_at",
    "media_image_url",
    "media_image_remotely_accessible",
    "media_title",
    "media_artist",
    "media_album_name",
    "media_album_artist",
    "media_track",
    "media_series_title",
    "media_season",
    "media_episode",
    "media_channel",
    "media_playlist",
    "app_id",
    "app_name",
    "source",
    "source_list",
    "sound_mode",
    "sound_mode_list",
    "shuffle",
    "repeat",
    "group_members",
    "supported_features",
}


@lru_cache
def _url_hash(url: str) -> str:
    """Create hash for media image url."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


class MediaPlayerEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """ABC for media player entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {
            MediaPlayerEntityStateAttribute.ENTITY_PICTURE_LOCAL,
            EntityStateAttribute.ENTITY_PICTURE,
            MediaPlayerEntityCapabilityAttribute.INPUT_SOURCE_LIST,
            MediaPlayerEntityStateAttribute.MEDIA_POSITION_UPDATED_AT,
            MediaPlayerEntityStateAttribute.MEDIA_POSITION,
            MediaPlayerEntityCapabilityAttribute.SOUND_MODE_LIST,
        }
    )

    entity_description: MediaPlayerEntityDescription
    _access_token: str | None = None

    _attr_app_id: str | None = None
    _attr_app_name: str | None = None
    _attr_device_class: MediaPlayerDeviceClass | None
    _attr_group_members: list[str] | None = None
    _attr_is_volume_muted: bool | None = None
    _attr_media_album_artist: str | None = None
    _attr_media_album_name: str | None = None
    _attr_media_artist: str | None = None
    _attr_media_channel: str | None = None
    _attr_media_content_id: str | None = None
    _attr_media_content_type: MediaType | str | None = None
    _attr_media_duration: int | None = None
    _attr_media_episode: str | None = None
    _attr_media_image_hash: str | None
    _attr_media_image_remotely_accessible: bool = False
    _attr_media_image_url: str | None = None
    _attr_media_playlist: str | None = None
    _attr_media_position_updated_at: dt.datetime | None = None
    _attr_media_position: int | None = None
    _attr_media_season: str | None = None
    _attr_media_series_title: str | None = None
    _attr_media_title: str | None = None
    _attr_media_track: int | None = None
    _attr_repeat: RepeatMode | str | None = None
    _attr_shuffle: bool | None = None
    _attr_sound_mode_list: list[str] | None = None
    _attr_sound_mode: str | None = None
    _attr_source_list: list[str] | None = None
    _attr_source: str | None = None
    _attr_state: MediaPlayerState | None = None
    _attr_supported_features: MediaPlayerEntityFeature = MediaPlayerEntityFeature(0)
    _attr_volume_level: float | None = None
    _attr_volume_step: float

    # Implement these for your media player
    @cached_property
    @override
    def device_class(self) -> MediaPlayerDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @cached_property
    @override
    def state(self) -> MediaPlayerState | None:
        """State of the player."""
        return self._attr_state

    @property
    def access_token(self) -> str:
        """Access token for this media player."""
        if self._access_token is None:
            self._access_token = secrets.token_hex(32)
        return self._access_token

    @cached_property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self._attr_volume_level

    @cached_property
    def volume_step(self) -> float:
        """Return the step to be used by the volume_up and volume_down services."""
        if hasattr(self, "_attr_volume_step"):
            return self._attr_volume_step
        if (
            hasattr(self, "entity_description")
            and (volume_step := self.entity_description.volume_step) is not None
        ):
            return volume_step
        return 0.1

    @cached_property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self._attr_is_volume_muted

    @cached_property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return self._attr_media_content_id

    @cached_property
    def media_content_type(self) -> MediaType | str | None:
        """Content type of current playing media."""
        return self._attr_media_content_type

    @cached_property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self._attr_media_duration

    @cached_property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self._attr_media_position

    @cached_property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self._attr_media_position_updated_at

    @cached_property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self._attr_media_image_url

    @cached_property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return self._attr_media_image_remotely_accessible

    @property
    def media_image_hash(self) -> str | None:
        """Hash value for media image."""
        if hasattr(self, "_attr_media_image_hash"):
            return self._attr_media_image_hash

        if (url := self.media_image_url) is not None:
            return _url_hash(url)

        return None

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch media image of current playing image."""
        if (url := self.media_image_url) is None:
            return None, None

        return await self._async_fetch_image_from_cache(url)

    async def async_get_browse_image(
        self,
        media_content_type: str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Optionally fetch internally accessible image for media browser.

        Must be implemented by integration.
        """
        return None, None

    @cached_property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._attr_media_title

    @cached_property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self._attr_media_artist

    @cached_property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self._attr_media_album_name

    @cached_property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        return self._attr_media_album_artist

    @cached_property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        return self._attr_media_track

    @cached_property
    def media_series_title(self) -> str | None:
        """Title of series of current playing media, TV show only."""
        return self._attr_media_series_title

    @cached_property
    def media_season(self) -> str | None:
        """Season of current playing media, TV show only."""
        return self._attr_media_season

    @cached_property
    def media_episode(self) -> str | None:
        """Episode of current playing media, TV show only."""
        return self._attr_media_episode

    @cached_property
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        return self._attr_media_channel

    @cached_property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        return self._attr_media_playlist

    @cached_property
    def app_id(self) -> str | None:
        """ID of the current running app."""
        return self._attr_app_id

    @cached_property
    def app_name(self) -> str | None:
        """Name of the current running app."""
        return self._attr_app_name

    @cached_property
    def source(self) -> str | None:
        """Name of the current input source."""
        return self._attr_source

    @cached_property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        return self._attr_source_list

    @cached_property
    def sound_mode(self) -> str | None:
        """Name of the current sound mode."""
        return self._attr_sound_mode

    @cached_property
    def sound_mode_list(self) -> list[str] | None:
        """List of available sound modes."""
        return self._attr_sound_mode_list

    @cached_property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        return self._attr_shuffle

    @cached_property
    def repeat(self) -> RepeatMode | str | None:
        """Return current repeat mode."""
        return self._attr_repeat

    @cached_property
    def group_members(self) -> list[str] | None:
        """List of members which are currently grouped together."""
        return self._attr_group_members

    @cached_property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return self._attr_supported_features

    def turn_on(self) -> None:
        """Turn the media player on."""
        raise NotImplementedError

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self.hass.async_add_executor_job(self.turn_on)

    def turn_off(self) -> None:
        """Turn the media player off."""
        raise NotImplementedError

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self.hass.async_add_executor_job(self.turn_off)

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        raise NotImplementedError

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.hass.async_add_executor_job(self.mute_volume, mute)

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        raise NotImplementedError

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.hass.async_add_executor_job(self.set_volume_level, volume)

    def media_play(self) -> None:
        """Send play command."""
        raise NotImplementedError

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.hass.async_add_executor_job(self.media_play)

    def media_pause(self) -> None:
        """Send pause command."""
        raise NotImplementedError

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.hass.async_add_executor_job(self.media_pause)

    def media_stop(self) -> None:
        """Send stop command."""
        raise NotImplementedError

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.hass.async_add_executor_job(self.media_stop)

    def media_previous_track(self) -> None:
        """Send previous track command."""
        raise NotImplementedError

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.hass.async_add_executor_job(self.media_previous_track)

    def media_next_track(self) -> None:
        """Send next track command."""
        raise NotImplementedError

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.hass.async_add_executor_job(self.media_next_track)

    def media_seek(self, position: float) -> None:
        """Send seek command."""
        raise NotImplementedError

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self.hass.async_add_executor_job(self.media_seek, position)

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        raise NotImplementedError

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        await self.hass.async_add_executor_job(
            ft.partial(self.play_media, media_type, media_id, **kwargs)
        )

    def select_source(self, source: str) -> None:
        """Select input source."""
        raise NotImplementedError

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.hass.async_add_executor_job(self.select_source, source)

    def select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        raise NotImplementedError

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        await self.hass.async_add_executor_job(self.select_sound_mode, sound_mode)

    def clear_playlist(self) -> None:
        """Clear players playlist."""
        raise NotImplementedError

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        await self.hass.async_add_executor_job(self.clear_playlist)

    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        raise NotImplementedError

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        await self.hass.async_add_executor_job(self.set_shuffle, shuffle)

    def set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        raise NotImplementedError

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self.hass.async_add_executor_job(self.set_repeat, repeat)

    # No need to overwrite these.
    @final
    @property
    def support_play(self) -> bool:
        """Boolean if play is supported."""
        return MediaPlayerEntityFeature.PLAY in self.supported_features

    @final
    @property
    def support_pause(self) -> bool:
        """Boolean if pause is supported."""
        return MediaPlayerEntityFeature.PAUSE in self.supported_features

    @final
    @property
    def support_stop(self) -> bool:
        """Boolean if stop is supported."""
        return MediaPlayerEntityFeature.STOP in self.supported_features

    @final
    @property
    def support_seek(self) -> bool:
        """Boolean if seek is supported."""
        return MediaPlayerEntityFeature.SEEK in self.supported_features

    @final
    @property
    def support_volume_set(self) -> bool:
        """Boolean if setting volume is supported."""
        return MediaPlayerEntityFeature.VOLUME_SET in self.supported_features

    @final
    @property
    def support_volume_mute(self) -> bool:
        """Boolean if muting volume is supported."""
        return MediaPlayerEntityFeature.VOLUME_MUTE in self.supported_features

    @final
    @property
    def support_previous_track(self) -> bool:
        """Boolean if previous track command supported."""
        return MediaPlayerEntityFeature.PREVIOUS_TRACK in self.supported_features

    @final
    @property
    def support_next_track(self) -> bool:
        """Boolean if next track command supported."""
        return MediaPlayerEntityFeature.NEXT_TRACK in self.supported_features

    @final
    @property
    def support_play_media(self) -> bool:
        """Boolean if play media command supported."""
        return MediaPlayerEntityFeature.PLAY_MEDIA in self.supported_features

    @final
    @property
    def support_select_source(self) -> bool:
        """Boolean if select source command supported."""
        return MediaPlayerEntityFeature.SELECT_SOURCE in self.supported_features

    @final
    @property
    def support_select_sound_mode(self) -> bool:
        """Boolean if select sound mode command supported."""
        return MediaPlayerEntityFeature.SELECT_SOUND_MODE in self.supported_features

    @final
    @property
    def support_clear_playlist(self) -> bool:
        """Boolean if clear playlist command supported."""
        return MediaPlayerEntityFeature.CLEAR_PLAYLIST in self.supported_features

    @final
    @property
    def support_shuffle_set(self) -> bool:
        """Boolean if shuffle is supported."""
        return MediaPlayerEntityFeature.SHUFFLE_SET in self.supported_features

    @final
    @property
    def support_grouping(self) -> bool:
        """Boolean if player grouping is supported."""
        return MediaPlayerEntityFeature.GROUPING in self.supported_features

    async def async_toggle(self) -> None:
        """Toggle the power on the media player."""
        if hasattr(self, "toggle"):
            await self.hass.async_add_executor_job(self.toggle)
            return

        if self.state in {
            MediaPlayerState.OFF,
            # Not comparing to MediaPlayerState.STANDBY to avoid deprecation warning
            "standby",
        }:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    async def async_volume_up(self) -> None:
        """Turn volume up for media player.

        This method is a coroutine.
        """
        if hasattr(self, "volume_up"):
            await self.hass.async_add_executor_job(self.volume_up)
            return

        if (
            self.volume_level is not None
            and self.volume_level < 1
            and MediaPlayerEntityFeature.VOLUME_SET in self.supported_features
        ):
            await self.async_set_volume_level(
                min(1, self.volume_level + self.volume_step)
            )

    async def async_volume_down(self) -> None:
        """Turn volume down for media player.

        This method is a coroutine.
        """
        if hasattr(self, "volume_down"):
            await self.hass.async_add_executor_job(self.volume_down)
            return

        if (
            self.volume_level is not None
            and self.volume_level > 0
            and MediaPlayerEntityFeature.VOLUME_SET in self.supported_features
        ):
            await self.async_set_volume_level(
                max(0, self.volume_level - self.volume_step)
            )

    async def async_media_play_pause(self) -> None:
        """Play or pause the media player."""
        if hasattr(self, "media_play_pause"):
            await self.hass.async_add_executor_job(self.media_play_pause)
            return

        if self.state == MediaPlayerState.PLAYING:
            await self.async_media_pause()
        else:
            await self.async_media_play()

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return image of the media playing."""
        if self.state == MediaPlayerState.OFF:
            return None

        if self.media_image_remotely_accessible:
            return self.media_image_url

        return self.media_image_local

    @property
    def media_image_local(self) -> str | None:
        """Return local url to media image."""
        if (image_hash := self.media_image_hash) is None:
            return None

        return (
            f"/api/media_player_proxy/{self.entity_id}?"
            f"token={self.access_token}&cache={image_hash}"
        )

    @property
    @override
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        data: dict[str, Any] = {}
        supported_features = self.supported_features

        if (
            source_list := self.source_list
        ) and MediaPlayerEntityFeature.SELECT_SOURCE in supported_features:
            data[MediaPlayerEntityCapabilityAttribute.INPUT_SOURCE_LIST] = source_list

        if (
            sound_mode_list := self.sound_mode_list
        ) and MediaPlayerEntityFeature.SELECT_SOUND_MODE in supported_features:
            data[MediaPlayerEntityCapabilityAttribute.SOUND_MODE_LIST] = sound_mode_list

        return data

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        state_attr: dict[str, Any] = {}

        if self.support_grouping:
            state_attr[MediaPlayerEntityStateAttribute.GROUP_MEMBERS] = (
                self.group_members
            )

        if self.state == MediaPlayerState.OFF:
            return state_attr

        for prop, attr in PROP_TO_ATTR.items():
            if (value := getattr(self, prop)) is not None:
                state_attr[attr] = value

        if self.media_image_remotely_accessible:
            state_attr[MediaPlayerEntityStateAttribute.ENTITY_PICTURE_LOCAL] = (
                self.media_image_local
            )

        return state_attr

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Return a BrowseMedia instance.

        The BrowseMedia instance will be used by the
        "media_player/browse_media" websocket command.
        """
        raise NotImplementedError

    async def async_internal_search_media(
        self,
        search_query: str,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
        media_filter_classes: list[MediaClass] | None = None,
    ) -> SearchMedia:
        """Search for media."""
        return await self.async_search_media(
            query=SearchMediaQuery(
                search_query=search_query,
                media_content_type=media_content_type,
                media_content_id=media_content_id,
                media_filter_classes=media_filter_classes,
            )
        )

    async def async_search_media(
        self,
        query: SearchMediaQuery,
    ) -> SearchMedia:
        """Search the media player."""
        raise NotImplementedError

    def join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        raise NotImplementedError

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        await self.hass.async_add_executor_job(self.join_players, group_members)

    def unjoin_player(self) -> None:
        """Remove this player from any group."""
        raise NotImplementedError

    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        await self.hass.async_add_executor_job(self.unjoin_player)

    async def _async_fetch_image_from_cache(
        self, url: str
    ) -> tuple[bytes | None, str | None]:
        """Fetch image.

        Images are cached in memory (the images are typically 10-100kB in size).
        """
        cache_images = _ENTITY_IMAGE_CACHE[CACHE_IMAGES]
        cache_maxsize = _ENTITY_IMAGE_CACHE[CACHE_MAXSIZE]

        if urlparse(url).hostname is None:
            url = f"{get_url(self.hass)}{url}"

        if url not in cache_images:
            cache_images[url] = {CACHE_LOCK: asyncio.Lock()}

        async with cache_images[url][CACHE_LOCK]:
            if CACHE_CONTENT in cache_images[url]:
                return cache_images[url][CACHE_CONTENT]

        (content, content_type) = await self._async_fetch_image(url)

        async with cache_images[url][CACHE_LOCK]:
            if content is not None:
                cache_images[url][CACHE_CONTENT] = content, content_type
            while len(cache_images) > cache_maxsize:
                cache_images.popitem(last=False)

        return content, content_type

    async def _async_fetch_image(self, url: str) -> tuple[bytes | None, str | None]:
        """Retrieve an image."""
        return await async_fetch_image(_LOGGER, self.hass, url)

    def get_browse_image_url(
        self,
        media_content_type: str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> str:
        """Generate an url for a media browser image."""
        url_path = (
            f"/api/media_player_proxy/{self.entity_id}/browse_media"
            # quote the media_content_id as it may contain url unsafe characters
            # aiohttp will unquote the path automatically
            f"/{media_content_type}/{quote(media_content_id)}"
        )

        url_query = {"token": self.access_token}
        if media_image_id:
            url_query["media_image_id"] = media_image_id

        return str(URL(url_path).with_query(url_query))


_FETCH_TIMEOUT = aiohttp.ClientTimeout(total=10)


def _image_response_appears_complete(
    response: aiohttp.ClientResponse, body: bytes
) -> bool:
    """Return False when the body is shorter than the advertised Content-Length."""
    # Content-Length is the encoded size; aiohttp may have decoded the body.
    encoding = (response.headers.get(CONTENT_ENCODING) or "identity").strip().lower()
    if encoding != "identity":
        return True
    content_length = response.headers.get(CONTENT_LENGTH)
    if content_length is None:
        return True
    try:
        return len(body) >= int(content_length)
    except ValueError:
        return True


async def async_fetch_image(
    logger: logging.Logger, hass: HomeAssistant, url: str
) -> tuple[bytes | None, str | None]:
    """Retrieve an image."""
    content, content_type = (None, None)
    websession = async_get_clientsession(hass)
    with suppress(TimeoutError):
        response = await websession.get(url, timeout=_FETCH_TIMEOUT)
        if response.status == HTTPStatus.OK:
            body = await response.read()
            if _image_response_appears_complete(response, body):
                content = body
                if content_type := response.headers.get(CONTENT_TYPE):
                    content_type = content_type.split(";")[0]

    if content is None:
        url_parts = URL(url)
        if url_parts.user is not None:
            url_parts = url_parts.with_user("xxxx")
        if url_parts.password is not None:
            url_parts = url_parts.with_password("xxxxxxxx")
        url = str(url_parts)
        logger.warning("Error retrieving proxied image from %s", url)

    return content, content_type
