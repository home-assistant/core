"""Component to interface with various media players."""
from __future__ import annotations

import asyncio
import collections
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import datetime as dt
import functools as ft
import hashlib
from http import HTTPStatus
import logging
import secrets
from typing import Any, Final, TypedDict, final
from urllib.parse import quote, urlparse

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL, CONTENT_TYPE
from aiohttp.typedefs import LooseHeaders
import async_timeout
from typing_extensions import Required
import voluptuous as vol
from yarl import URL

from homeassistant.backports.enum import StrEnum
from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.components.websocket_api import ERR_NOT_SUPPORTED, ERR_UNKNOWN_ERROR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_IDLE,
    STATE_OFF,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.network import get_url
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .browse_media import BrowseMedia, async_process_play_media_url  # noqa: F401
from .const import (  # noqa: F401
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_ENTITY_PICTURE_LOCAL,
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_PLAYLIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEASON,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SERIES_TITLE,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    CONTENT_AUTH_EXPIRY_TIME,
    DOMAIN,
    MEDIA_CLASS_DIRECTORY,
    REPEAT_MODES,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_UNJOIN,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_GROUPING,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    MediaClass,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from .errors import BrowseError

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

CACHE_IMAGES: Final = "images"
CACHE_MAXSIZE: Final = "maxsize"
CACHE_LOCK: Final = "lock"
CACHE_URL: Final = "url"
CACHE_CONTENT: Final = "content"

SCAN_INTERVAL = dt.timedelta(seconds=10)


class MediaPlayerEnqueue(StrEnum):
    """Enqueue types for playing media."""

    # add given media item to end of the queue
    ADD = "add"
    # play the given media item next, keep queue
    NEXT = "next"
    # play the given media item now, keep queue
    PLAY = "play"
    # play the given media item now, clear queue
    REPLACE = "replace"


class MediaPlayerDeviceClass(StrEnum):
    """Device class for media players."""

    TV = "tv"
    SPEAKER = "speaker"
    RECEIVER = "receiver"


DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.Coerce(MediaPlayerDeviceClass))


# DEVICE_CLASS* below are deprecated as of 2021.12
# use the MediaPlayerDeviceClass enum instead.
DEVICE_CLASSES = [cls.value for cls in MediaPlayerDeviceClass]
DEVICE_CLASS_TV = MediaPlayerDeviceClass.TV.value
DEVICE_CLASS_SPEAKER = MediaPlayerDeviceClass.SPEAKER.value
DEVICE_CLASS_RECEIVER = MediaPlayerDeviceClass.RECEIVER.value


MEDIA_PLAYER_PLAY_MEDIA_SCHEMA = {
    vol.Required(ATTR_MEDIA_CONTENT_TYPE): cv.string,
    vol.Required(ATTR_MEDIA_CONTENT_ID): cv.string,
    vol.Exclusive(ATTR_MEDIA_ENQUEUE, "enqueue_announce"): vol.Any(
        cv.boolean, vol.Coerce(MediaPlayerEnqueue)
    ),
    vol.Exclusive(ATTR_MEDIA_ANNOUNCE, "enqueue_announce"): cv.boolean,
    vol.Optional(ATTR_MEDIA_EXTRA, default={}): dict,
}

ATTR_TO_PROPERTY = [
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_SERIES_TITLE,
    ATTR_MEDIA_SEASON,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_PLAYLIST,
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_SOUND_MODE,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_REPEAT,
]

# mypy: disallow-any-generics


class _CacheImage(TypedDict, total=False):
    """Class to hold a cached image."""

    lock: Required[asyncio.Lock]
    content: tuple[bytes | None, str | None]


class _ImageCache(TypedDict):
    """Class to hold a cached image."""

    images: collections.OrderedDict[str, _CacheImage]
    maxsize: int


_ENTITY_IMAGE_CACHE = _ImageCache(images=collections.OrderedDict(), maxsize=16)


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str | None = None) -> bool:
    """
    Return true if specified media player entity_id is on.

    Check all media player if no entity_id specified.
    """
    entity_ids = [entity_id] if entity_id else hass.states.entity_ids(DOMAIN)
    return any(
        not hass.states.is_state(entity_id, MediaPlayerState.OFF)
        for entity_id in entity_ids
    )


def _rename_keys(**keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Create validator that renames keys.

    Necessary because the service schema names do not match the command parameters.

    Async friendly.
    """

    def rename(value: dict[str, Any]) -> dict[str, Any]:
        for to_key, from_key in keys.items():
            if from_key in value:
                value[to_key] = value.pop(from_key)
        return value

    return rename


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for media_players."""
    component = hass.data[DOMAIN] = EntityComponent[MediaPlayerEntity](
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL
    )

    websocket_api.async_register_command(hass, websocket_browse_media)
    hass.http.register_view(MediaPlayerImageView(component))

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON, {}, "async_turn_on", [MediaPlayerEntityFeature.TURN_ON]
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, {}, "async_turn_off", [MediaPlayerEntityFeature.TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE,
        {},
        "async_toggle",
        [MediaPlayerEntityFeature.TURN_OFF | MediaPlayerEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_UP,
        {},
        "async_volume_up",
        [MediaPlayerEntityFeature.VOLUME_SET, MediaPlayerEntityFeature.VOLUME_STEP],
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_DOWN,
        {},
        "async_volume_down",
        [MediaPlayerEntityFeature.VOLUME_SET, MediaPlayerEntityFeature.VOLUME_STEP],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PLAY_PAUSE,
        {},
        "async_media_play_pause",
        [MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PLAY, {}, "async_media_play", [MediaPlayerEntityFeature.PLAY]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PAUSE, {}, "async_media_pause", [MediaPlayerEntityFeature.PAUSE]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_STOP, {}, "async_media_stop", [MediaPlayerEntityFeature.STOP]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_NEXT_TRACK,
        {},
        "async_media_next_track",
        [MediaPlayerEntityFeature.NEXT_TRACK],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {},
        "async_media_previous_track",
        [MediaPlayerEntityFeature.PREVIOUS_TRACK],
    )
    component.async_register_entity_service(
        SERVICE_CLEAR_PLAYLIST,
        {},
        "async_clear_playlist",
        [MediaPlayerEntityFeature.CLEAR_PLAYLIST],
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_SET,
        vol.All(
            cv.make_entity_service_schema(
                {vol.Required(ATTR_MEDIA_VOLUME_LEVEL): cv.small_float}
            ),
            _rename_keys(volume=ATTR_MEDIA_VOLUME_LEVEL),
        ),
        "async_set_volume_level",
        [MediaPlayerEntityFeature.VOLUME_SET],
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_MUTE,
        vol.All(
            cv.make_entity_service_schema(
                {vol.Required(ATTR_MEDIA_VOLUME_MUTED): cv.boolean}
            ),
            _rename_keys(mute=ATTR_MEDIA_VOLUME_MUTED),
        ),
        "async_mute_volume",
        [MediaPlayerEntityFeature.VOLUME_MUTE],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_SEEK,
        vol.All(
            cv.make_entity_service_schema(
                {vol.Required(ATTR_MEDIA_SEEK_POSITION): cv.positive_float}
            ),
            _rename_keys(position=ATTR_MEDIA_SEEK_POSITION),
        ),
        "async_media_seek",
        [MediaPlayerEntityFeature.SEEK],
    )
    component.async_register_entity_service(
        SERVICE_JOIN,
        {vol.Required(ATTR_GROUP_MEMBERS): vol.All(cv.ensure_list, [cv.entity_id])},
        "async_join_players",
        [MediaPlayerEntityFeature.GROUPING],
    )
    component.async_register_entity_service(
        SERVICE_SELECT_SOURCE,
        {vol.Required(ATTR_INPUT_SOURCE): cv.string},
        "async_select_source",
        [MediaPlayerEntityFeature.SELECT_SOURCE],
    )
    component.async_register_entity_service(
        SERVICE_SELECT_SOUND_MODE,
        {vol.Required(ATTR_SOUND_MODE): cv.string},
        "async_select_sound_mode",
        [MediaPlayerEntityFeature.SELECT_SOUND_MODE],
    )

    # Remove in Home Assistant 2022.9
    def _rewrite_enqueue(value: dict[str, Any]) -> dict[str, Any]:
        """Rewrite the enqueue value."""
        if ATTR_MEDIA_ENQUEUE not in value:
            pass
        elif value[ATTR_MEDIA_ENQUEUE] is True:
            value[ATTR_MEDIA_ENQUEUE] = MediaPlayerEnqueue.ADD
            _LOGGER.warning(
                "Playing media with enqueue set to True is deprecated. Use 'add' instead"
            )
        elif value[ATTR_MEDIA_ENQUEUE] is False:
            value[ATTR_MEDIA_ENQUEUE] = MediaPlayerEnqueue.PLAY
            _LOGGER.warning(
                "Playing media with enqueue set to False is deprecated. Use 'play' instead"
            )

        return value

    component.async_register_entity_service(
        SERVICE_PLAY_MEDIA,
        vol.All(
            cv.make_entity_service_schema(MEDIA_PLAYER_PLAY_MEDIA_SCHEMA),
            _rewrite_enqueue,
            _rename_keys(
                media_type=ATTR_MEDIA_CONTENT_TYPE,
                media_id=ATTR_MEDIA_CONTENT_ID,
                enqueue=ATTR_MEDIA_ENQUEUE,
            ),
        ),
        "async_play_media",
        [MediaPlayerEntityFeature.PLAY_MEDIA],
    )
    component.async_register_entity_service(
        SERVICE_SHUFFLE_SET,
        {vol.Required(ATTR_MEDIA_SHUFFLE): cv.boolean},
        "async_set_shuffle",
        [MediaPlayerEntityFeature.SHUFFLE_SET],
    )
    component.async_register_entity_service(
        SERVICE_UNJOIN, {}, "async_unjoin_player", [MediaPlayerEntityFeature.GROUPING]
    )

    component.async_register_entity_service(
        SERVICE_REPEAT_SET,
        {vol.Required(ATTR_MEDIA_REPEAT): vol.Coerce(RepeatMode)},
        "async_set_repeat",
        [MediaPlayerEntityFeature.REPEAT_SET],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[MediaPlayerEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[MediaPlayerEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class MediaPlayerEntityDescription(EntityDescription):
    """A class that describes media player entities."""

    device_class: MediaPlayerDeviceClass | str | None = None


class MediaPlayerEntity(Entity):
    """ABC for media player entities."""

    entity_description: MediaPlayerEntityDescription
    _access_token: str | None = None

    _attr_app_id: str | None = None
    _attr_app_name: str | None = None
    _attr_device_class: MediaPlayerDeviceClass | str | None
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
    _attr_state: MediaPlayerState | str | None = None
    _attr_supported_features: int = 0
    _attr_volume_level: float | None = None

    # Implement these for your media player
    @property
    def device_class(self) -> MediaPlayerDeviceClass | str | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @property
    def state(self) -> MediaPlayerState | str | None:
        """State of the player."""
        return self._attr_state

    @property
    def access_token(self) -> str:
        """Access token for this media player."""
        if self._access_token is None:
            self._access_token = secrets.token_hex(32)
        return self._access_token

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self._attr_volume_level

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self._attr_is_volume_muted

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return self._attr_media_content_id

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Content type of current playing media."""
        return self._attr_media_content_type

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self._attr_media_duration

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self._attr_media_position

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self._attr_media_position_updated_at

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self._attr_media_image_url

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return self._attr_media_image_remotely_accessible

    @property
    def media_image_hash(self) -> str | None:
        """Hash value for media image."""
        if hasattr(self, "_attr_media_image_hash"):
            return self._attr_media_image_hash

        if (url := self.media_image_url) is not None:
            return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

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
        """
        Optionally fetch internally accessible image for media browser.

        Must be implemented by integration.
        """
        return None, None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._attr_media_title

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self._attr_media_artist

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self._attr_media_album_name

    @property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        return self._attr_media_album_artist

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        return self._attr_media_track

    @property
    def media_series_title(self) -> str | None:
        """Title of series of current playing media, TV show only."""
        return self._attr_media_series_title

    @property
    def media_season(self) -> str | None:
        """Season of current playing media, TV show only."""
        return self._attr_media_season

    @property
    def media_episode(self) -> str | None:
        """Episode of current playing media, TV show only."""
        return self._attr_media_episode

    @property
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        return self._attr_media_channel

    @property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        return self._attr_media_playlist

    @property
    def app_id(self) -> str | None:
        """ID of the current running app."""
        return self._attr_app_id

    @property
    def app_name(self) -> str | None:
        """Name of the current running app."""
        return self._attr_app_name

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        return self._attr_source

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        return self._attr_source_list

    @property
    def sound_mode(self) -> str | None:
        """Name of the current sound mode."""
        return self._attr_sound_mode

    @property
    def sound_mode_list(self) -> list[str] | None:
        """List of available sound modes."""
        return self._attr_sound_mode_list

    @property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        return self._attr_shuffle

    @property
    def repeat(self) -> RepeatMode | str | None:
        """Return current repeat mode."""
        return self._attr_repeat

    @property
    def group_members(self) -> list[str] | None:
        """List of members which are currently grouped together."""
        return self._attr_group_members

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        return self._attr_supported_features

    def turn_on(self) -> None:
        """Turn the media player on."""
        raise NotImplementedError()

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self.hass.async_add_executor_job(self.turn_on)

    def turn_off(self) -> None:
        """Turn the media player off."""
        raise NotImplementedError()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self.hass.async_add_executor_job(self.turn_off)

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        raise NotImplementedError()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.hass.async_add_executor_job(self.mute_volume, mute)

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        raise NotImplementedError()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.hass.async_add_executor_job(self.set_volume_level, volume)

    def media_play(self) -> None:
        """Send play command."""
        raise NotImplementedError()

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.hass.async_add_executor_job(self.media_play)

    def media_pause(self) -> None:
        """Send pause command."""
        raise NotImplementedError()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.hass.async_add_executor_job(self.media_pause)

    def media_stop(self) -> None:
        """Send stop command."""
        raise NotImplementedError()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.hass.async_add_executor_job(self.media_stop)

    def media_previous_track(self) -> None:
        """Send previous track command."""
        raise NotImplementedError()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.hass.async_add_executor_job(self.media_previous_track)

    def media_next_track(self) -> None:
        """Send next track command."""
        raise NotImplementedError()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.hass.async_add_executor_job(self.media_next_track)

    def media_seek(self, position: float) -> None:
        """Send seek command."""
        raise NotImplementedError()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self.hass.async_add_executor_job(self.media_seek, position)

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        raise NotImplementedError()

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        await self.hass.async_add_executor_job(
            ft.partial(self.play_media, media_type, media_id, **kwargs)
        )

    def select_source(self, source: str) -> None:
        """Select input source."""
        raise NotImplementedError()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.hass.async_add_executor_job(self.select_source, source)

    def select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        raise NotImplementedError()

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        await self.hass.async_add_executor_job(self.select_sound_mode, sound_mode)

    def clear_playlist(self) -> None:
        """Clear players playlist."""
        raise NotImplementedError()

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        await self.hass.async_add_executor_job(self.clear_playlist)

    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        raise NotImplementedError()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        await self.hass.async_add_executor_job(self.set_shuffle, shuffle)

    def set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        raise NotImplementedError()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self.hass.async_add_executor_job(self.set_repeat, repeat)

    # No need to overwrite these.
    @final
    @property
    def support_play(self) -> bool:
        """Boolean if play is supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.PLAY)

    @final
    @property
    def support_pause(self) -> bool:
        """Boolean if pause is supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.PAUSE)

    @final
    @property
    def support_stop(self) -> bool:
        """Boolean if stop is supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.STOP)

    @final
    @property
    def support_seek(self) -> bool:
        """Boolean if seek is supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.SEEK)

    @final
    @property
    def support_volume_set(self) -> bool:
        """Boolean if setting volume is supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.VOLUME_SET)

    @final
    @property
    def support_volume_mute(self) -> bool:
        """Boolean if muting volume is supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.VOLUME_MUTE)

    @final
    @property
    def support_previous_track(self) -> bool:
        """Boolean if previous track command supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.PREVIOUS_TRACK)

    @final
    @property
    def support_next_track(self) -> bool:
        """Boolean if next track command supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.NEXT_TRACK)

    @final
    @property
    def support_play_media(self) -> bool:
        """Boolean if play media command supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.PLAY_MEDIA)

    @final
    @property
    def support_select_source(self) -> bool:
        """Boolean if select source command supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.SELECT_SOURCE)

    @final
    @property
    def support_select_sound_mode(self) -> bool:
        """Boolean if select sound mode command supported."""
        return bool(
            self.supported_features & MediaPlayerEntityFeature.SELECT_SOUND_MODE
        )

    @final
    @property
    def support_clear_playlist(self) -> bool:
        """Boolean if clear playlist command supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.CLEAR_PLAYLIST)

    @final
    @property
    def support_shuffle_set(self) -> bool:
        """Boolean if shuffle is supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.SHUFFLE_SET)

    @final
    @property
    def support_grouping(self) -> bool:
        """Boolean if player grouping is supported."""
        return bool(self.supported_features & MediaPlayerEntityFeature.GROUPING)

    async def async_toggle(self) -> None:
        """Toggle the power on the media player."""
        if hasattr(self, "toggle"):
            await self.hass.async_add_executor_job(
                self.toggle  # type: ignore[attr-defined]
            )
            return

        if self.state in {
            MediaPlayerState.OFF,
            MediaPlayerState.IDLE,
            MediaPlayerState.STANDBY,
        }:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    async def async_volume_up(self) -> None:
        """Turn volume up for media player.

        This method is a coroutine.
        """
        if hasattr(self, "volume_up"):
            await self.hass.async_add_executor_job(
                self.volume_up  # type: ignore[attr-defined]
            )
            return

        if (
            self.volume_level is not None
            and self.volume_level < 1
            and self.supported_features & MediaPlayerEntityFeature.VOLUME_SET
        ):
            await self.async_set_volume_level(min(1, self.volume_level + 0.1))

    async def async_volume_down(self) -> None:
        """Turn volume down for media player.

        This method is a coroutine.
        """
        if hasattr(self, "volume_down"):
            await self.hass.async_add_executor_job(
                self.volume_down  # type: ignore[attr-defined]
            )
            return

        if (
            self.volume_level is not None
            and self.volume_level > 0
            and self.supported_features & MediaPlayerEntityFeature.VOLUME_SET
        ):
            await self.async_set_volume_level(max(0, self.volume_level - 0.1))

    async def async_media_play_pause(self) -> None:
        """Play or pause the media player."""
        if hasattr(self, "media_play_pause"):
            await self.hass.async_add_executor_job(
                self.media_play_pause  # type: ignore[attr-defined]
            )
            return

        if self.state == MediaPlayerState.PLAYING:
            await self.async_media_pause()
        else:
            await self.async_media_play()

    @property
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
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        supported_features = self.supported_features or 0
        data: dict[str, Any] = {}

        if supported_features & MediaPlayerEntityFeature.SELECT_SOURCE and (
            source_list := self.source_list
        ):
            data[ATTR_INPUT_SOURCE_LIST] = source_list

        if supported_features & MediaPlayerEntityFeature.SELECT_SOUND_MODE and (
            sound_mode_list := self.sound_mode_list
        ):
            data[ATTR_SOUND_MODE_LIST] = sound_mode_list

        return data

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        state_attr: dict[str, Any] = {}

        if self.support_grouping:
            state_attr[ATTR_GROUP_MEMBERS] = self.group_members

        if self.state == MediaPlayerState.OFF:
            return state_attr

        for attr in ATTR_TO_PROPERTY:
            if (value := getattr(self, attr)) is not None:
                state_attr[attr] = value

        if self.media_image_remotely_accessible:
            state_attr[ATTR_ENTITY_PICTURE_LOCAL] = self.media_image_local

        return state_attr

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Return a BrowseMedia instance.

        The BrowseMedia instance will be used by the
        "media_player/browse_media" websocket command.
        """
        raise NotImplementedError()

    def join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        raise NotImplementedError()

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        await self.hass.async_add_executor_job(self.join_players, group_members)

    def unjoin_player(self) -> None:
        """Remove this player from any group."""
        raise NotImplementedError()

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


class MediaPlayerImageView(HomeAssistantView):
    """Media player view to serve an image."""

    requires_auth = False
    url = "/api/media_player_proxy/{entity_id}"
    name = "api:media_player:image"
    extra_urls = [
        # Need to modify the default regex for media_content_id as it may
        # include arbitrary characters including '/','{', or '}'
        url
        + "/browse_media/{media_content_type}/{media_content_id:.+}",
    ]

    def __init__(self, component: EntityComponent[MediaPlayerEntity]) -> None:
        """Initialize a media player view."""
        self.component = component

    async def get(
        self,
        request: web.Request,
        entity_id: str,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> web.Response:
        """Start a get request."""
        if (player := self.component.get_entity(entity_id)) is None:
            status = (
                HTTPStatus.NOT_FOUND
                if request[KEY_AUTHENTICATED]
                else HTTPStatus.UNAUTHORIZED
            )
            return web.Response(status=status)

        assert isinstance(player, MediaPlayerEntity)
        authenticated = (
            request[KEY_AUTHENTICATED]
            or request.query.get("token") == player.access_token
        )

        if not authenticated:
            return web.Response(status=HTTPStatus.UNAUTHORIZED)

        if media_content_type and media_content_id:
            media_image_id = request.query.get("media_image_id")
            data, content_type = await player.async_get_browse_image(
                media_content_type, media_content_id, media_image_id
            )
        else:
            data, content_type = await player.async_get_media_image()

        if data is None:
            return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

        headers: LooseHeaders = {CACHE_CONTROL: "max-age=3600"}
        return web.Response(body=data, content_type=content_type, headers=headers)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "media_player/browse_media",
        vol.Required("entity_id"): cv.entity_id,
        vol.Inclusive(
            ATTR_MEDIA_CONTENT_TYPE,
            "media_ids",
            "media_content_type and media_content_id must be provided together",
        ): str,
        vol.Inclusive(
            ATTR_MEDIA_CONTENT_ID,
            "media_ids",
            "media_content_type and media_content_id must be provided together",
        ): str,
    }
)
@websocket_api.async_response
async def websocket_browse_media(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """
    Browse media available to the media_player entity.

    To use, media_player integrations can implement MediaPlayerEntity.async_browse_media()
    """
    component: EntityComponent[MediaPlayerEntity] = hass.data[DOMAIN]
    player = component.get_entity(msg["entity_id"])

    if player is None:
        connection.send_error(msg["id"], "entity_not_found", "Entity not found")
        return

    if not player.supported_features & MediaPlayerEntityFeature.BROWSE_MEDIA:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], ERR_NOT_SUPPORTED, "Player does not support browsing media"
            )
        )
        return

    media_content_type = msg.get(ATTR_MEDIA_CONTENT_TYPE)
    media_content_id = msg.get(ATTR_MEDIA_CONTENT_ID)

    try:
        payload = await player.async_browse_media(media_content_type, media_content_id)
    except NotImplementedError:
        assert player.platform
        _LOGGER.error(
            "%s allows media browsing but its integration (%s) does not",
            player.entity_id,
            player.platform.platform_name,
        )
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                ERR_NOT_SUPPORTED,
                "Integration does not support browsing media",
            )
        )
        return
    except BrowseError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], ERR_UNKNOWN_ERROR, str(err))
        )
        return

    # For backwards compat
    if isinstance(payload, BrowseMedia):
        result = payload.as_dict()
    else:
        result = payload  # type: ignore[unreachable]
        _LOGGER.warning("Browse Media should use new BrowseMedia class")

    connection.send_result(msg["id"], result)


async def async_fetch_image(
    logger: logging.Logger, hass: HomeAssistant, url: str
) -> tuple[bytes | None, str | None]:
    """Retrieve an image."""
    content, content_type = (None, None)
    websession = async_get_clientsession(hass)
    with suppress(asyncio.TimeoutError), async_timeout.timeout(10):
        response = await websession.get(url)
        if response.status == HTTPStatus.OK:
            content = await response.read()
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
