"""Component to interface with various media players."""
import asyncio
import base64
import collections
from datetime import timedelta
import functools as ft
import hashlib
import logging
from random import SystemRandom
from typing import Optional
from urllib.parse import urlparse

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL, CONTENT_TYPE
from aiohttp.typedefs import LooseHeaders
import async_timeout
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.const import (
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    HTTP_OK,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
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
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.network import get_url
from homeassistant.loader import bind_hass

from .const import (
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_PLAYLIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
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
    DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
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
)

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)
_RND = SystemRandom()

ENTITY_ID_FORMAT = DOMAIN + ".{}"

CACHE_IMAGES = "images"
CACHE_MAXSIZE = "maxsize"
CACHE_LOCK = "lock"
CACHE_URL = "url"
CACHE_CONTENT = "content"
ENTITY_IMAGE_CACHE = {CACHE_IMAGES: collections.OrderedDict(), CACHE_MAXSIZE: 16}

SCAN_INTERVAL = timedelta(seconds=10)

DEVICE_CLASS_TV = "tv"
DEVICE_CLASS_SPEAKER = "speaker"

DEVICE_CLASSES = [DEVICE_CLASS_TV, DEVICE_CLASS_SPEAKER]

DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))


MEDIA_PLAYER_PLAY_MEDIA_SCHEMA = {
    vol.Required(ATTR_MEDIA_CONTENT_TYPE): cv.string,
    vol.Required(ATTR_MEDIA_CONTENT_ID): cv.string,
    vol.Optional(ATTR_MEDIA_ENQUEUE): cv.boolean,
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
]


@bind_hass
def is_on(hass, entity_id=None):
    """
    Return true if specified media player entity_id is on.

    Check all media player if no entity_id specified.
    """
    entity_ids = [entity_id] if entity_id else hass.states.entity_ids(DOMAIN)
    return any(
        not hass.states.is_state(entity_id, STATE_OFF) for entity_id in entity_ids
    )


WS_TYPE_MEDIA_PLAYER_THUMBNAIL = "media_player_thumbnail"
SCHEMA_WEBSOCKET_GET_THUMBNAIL = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {"type": WS_TYPE_MEDIA_PLAYER_THUMBNAIL, "entity_id": cv.entity_id}
)


def _rename_keys(**keys):
    """Create validator that renames keys.

    Necessary because the service schema names do not match the command parameters.

    Async friendly.
    """

    def rename(value):
        for to_key, from_key in keys.items():
            if from_key in value:
                value[to_key] = value.pop(from_key)
        return value

    return rename


async def async_setup(hass, config):
    """Track states and offer events for media_players."""
    component = hass.data[DOMAIN] = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL
    )

    hass.components.websocket_api.async_register_command(
        WS_TYPE_MEDIA_PLAYER_THUMBNAIL,
        websocket_handle_thumbnail,
        SCHEMA_WEBSOCKET_GET_THUMBNAIL,
    )
    hass.http.register_view(MediaPlayerImageView(component))

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON, {}, "async_turn_on", [SUPPORT_TURN_ON]
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, {}, "async_turn_off", [SUPPORT_TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE, {}, "async_toggle", [SUPPORT_TURN_OFF | SUPPORT_TURN_ON]
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_UP,
        {},
        "async_volume_up",
        [SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP],
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_DOWN,
        {},
        "async_volume_down",
        [SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PLAY_PAUSE,
        {},
        "async_media_play_pause",
        [SUPPORT_PLAY | SUPPORT_PAUSE],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PLAY, {}, "async_media_play", [SUPPORT_PLAY]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PAUSE, {}, "async_media_pause", [SUPPORT_PAUSE]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_STOP, {}, "async_media_stop", [SUPPORT_STOP]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_NEXT_TRACK, {}, "async_media_next_track", [SUPPORT_NEXT_TRACK]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {},
        "async_media_previous_track",
        [SUPPORT_PREVIOUS_TRACK],
    )
    component.async_register_entity_service(
        SERVICE_CLEAR_PLAYLIST, {}, "async_clear_playlist", [SUPPORT_CLEAR_PLAYLIST]
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
        [SUPPORT_VOLUME_SET],
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
        [SUPPORT_VOLUME_MUTE],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_SEEK,
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Required(ATTR_MEDIA_SEEK_POSITION): vol.All(
                        vol.Coerce(float), vol.Range(min=0)
                    )
                }
            ),
            _rename_keys(position=ATTR_MEDIA_SEEK_POSITION),
        ),
        "async_media_seek",
        [SUPPORT_SEEK],
    )
    component.async_register_entity_service(
        SERVICE_SELECT_SOURCE,
        {vol.Required(ATTR_INPUT_SOURCE): cv.string},
        "async_select_source",
        [SUPPORT_SELECT_SOURCE],
    )
    component.async_register_entity_service(
        SERVICE_SELECT_SOUND_MODE,
        {vol.Required(ATTR_SOUND_MODE): cv.string},
        "async_select_sound_mode",
        [SUPPORT_SELECT_SOUND_MODE],
    )
    component.async_register_entity_service(
        SERVICE_PLAY_MEDIA,
        vol.All(
            cv.make_entity_service_schema(MEDIA_PLAYER_PLAY_MEDIA_SCHEMA),
            _rename_keys(
                media_type=ATTR_MEDIA_CONTENT_TYPE,
                media_id=ATTR_MEDIA_CONTENT_ID,
                enqueue=ATTR_MEDIA_ENQUEUE,
            ),
        ),
        "async_play_media",
        [SUPPORT_PLAY_MEDIA],
    )
    component.async_register_entity_service(
        SERVICE_SHUFFLE_SET,
        {vol.Required(ATTR_MEDIA_SHUFFLE): cv.boolean},
        "async_set_shuffle",
        [SUPPORT_SHUFFLE_SET],
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class MediaPlayerEntity(Entity):
    """ABC for media player entities."""

    _access_token: Optional[str] = None

    # Implement these for your media player
    @property
    def state(self):
        """State of the player."""
        return None

    @property
    def access_token(self) -> str:
        """Access token for this media player."""
        if self._access_token is None:
            self._access_token = hashlib.sha256(
                _RND.getrandbits(256).to_bytes(32, "little")
            ).hexdigest()
        return self._access_token

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return None

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return None

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return None

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return None

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return False

    @property
    def media_image_hash(self):
        """Hash value for media image."""
        url = self.media_image_url
        if url is not None:
            return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

        return None

    async def async_get_media_image(self):
        """Fetch media image of current playing image."""
        url = self.media_image_url
        if url is None:
            return None, None

        return await _async_fetch_image(self.hass, url)

    @property
    def media_title(self):
        """Title of current playing media."""
        return None

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return None

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return None

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        return None

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return None

    @property
    def media_series_title(self):
        """Title of series of current playing media, TV show only."""
        return None

    @property
    def media_season(self):
        """Season of current playing media, TV show only."""
        return None

    @property
    def media_episode(self):
        """Episode of current playing media, TV show only."""
        return None

    @property
    def media_channel(self):
        """Channel currently playing."""
        return None

    @property
    def media_playlist(self):
        """Title of Playlist currently playing."""
        return None

    @property
    def app_id(self):
        """ID of the current running app."""
        return None

    @property
    def app_name(self):
        """Name of the current running app."""
        return None

    @property
    def source(self):
        """Name of the current input source."""
        return None

    @property
    def source_list(self):
        """List of available input sources."""
        return None

    @property
    def sound_mode(self):
        """Name of the current sound mode."""
        return None

    @property
    def sound_mode_list(self):
        """List of available sound modes."""
        return None

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return 0

    def turn_on(self):
        """Turn the media player on."""
        raise NotImplementedError()

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.hass.async_add_job(self.turn_on)

    def turn_off(self):
        """Turn the media player off."""
        raise NotImplementedError()

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.hass.async_add_job(self.turn_off)

    def mute_volume(self, mute):
        """Mute the volume."""
        raise NotImplementedError()

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        await self.hass.async_add_job(self.mute_volume, mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        raise NotImplementedError()

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self.hass.async_add_job(self.set_volume_level, volume)

    def media_play(self):
        """Send play command."""
        raise NotImplementedError()

    async def async_media_play(self):
        """Send play command."""
        await self.hass.async_add_job(self.media_play)

    def media_pause(self):
        """Send pause command."""
        raise NotImplementedError()

    async def async_media_pause(self):
        """Send pause command."""
        await self.hass.async_add_job(self.media_pause)

    def media_stop(self):
        """Send stop command."""
        raise NotImplementedError()

    async def async_media_stop(self):
        """Send stop command."""
        await self.hass.async_add_job(self.media_stop)

    def media_previous_track(self):
        """Send previous track command."""
        raise NotImplementedError()

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self.hass.async_add_job(self.media_previous_track)

    def media_next_track(self):
        """Send next track command."""
        raise NotImplementedError()

    async def async_media_next_track(self):
        """Send next track command."""
        await self.hass.async_add_job(self.media_next_track)

    def media_seek(self, position):
        """Send seek command."""
        raise NotImplementedError()

    async def async_media_seek(self, position):
        """Send seek command."""
        await self.hass.async_add_job(self.media_seek, position)

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        raise NotImplementedError()

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        await self.hass.async_add_job(
            ft.partial(self.play_media, media_type, media_id, **kwargs)
        )

    def select_source(self, source):
        """Select input source."""
        raise NotImplementedError()

    async def async_select_source(self, source):
        """Select input source."""
        await self.hass.async_add_job(self.select_source, source)

    def select_sound_mode(self, sound_mode):
        """Select sound mode."""
        raise NotImplementedError()

    async def async_select_sound_mode(self, sound_mode):
        """Select sound mode."""
        await self.hass.async_add_job(self.select_sound_mode, sound_mode)

    def clear_playlist(self):
        """Clear players playlist."""
        raise NotImplementedError()

    async def async_clear_playlist(self):
        """Clear players playlist."""
        await self.hass.async_add_job(self.clear_playlist)

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        raise NotImplementedError()

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self.hass.async_add_job(self.set_shuffle, shuffle)

    # No need to overwrite these.
    @property
    def support_play(self):
        """Boolean if play is supported."""
        return bool(self.supported_features & SUPPORT_PLAY)

    @property
    def support_pause(self):
        """Boolean if pause is supported."""
        return bool(self.supported_features & SUPPORT_PAUSE)

    @property
    def support_stop(self):
        """Boolean if stop is supported."""
        return bool(self.supported_features & SUPPORT_STOP)

    @property
    def support_seek(self):
        """Boolean if seek is supported."""
        return bool(self.supported_features & SUPPORT_SEEK)

    @property
    def support_volume_set(self):
        """Boolean if setting volume is supported."""
        return bool(self.supported_features & SUPPORT_VOLUME_SET)

    @property
    def support_volume_mute(self):
        """Boolean if muting volume is supported."""
        return bool(self.supported_features & SUPPORT_VOLUME_MUTE)

    @property
    def support_previous_track(self):
        """Boolean if previous track command supported."""
        return bool(self.supported_features & SUPPORT_PREVIOUS_TRACK)

    @property
    def support_next_track(self):
        """Boolean if next track command supported."""
        return bool(self.supported_features & SUPPORT_NEXT_TRACK)

    @property
    def support_play_media(self):
        """Boolean if play media command supported."""
        return bool(self.supported_features & SUPPORT_PLAY_MEDIA)

    @property
    def support_select_source(self):
        """Boolean if select source command supported."""
        return bool(self.supported_features & SUPPORT_SELECT_SOURCE)

    @property
    def support_select_sound_mode(self):
        """Boolean if select sound mode command supported."""
        return bool(self.supported_features & SUPPORT_SELECT_SOUND_MODE)

    @property
    def support_clear_playlist(self):
        """Boolean if clear playlist command supported."""
        return bool(self.supported_features & SUPPORT_CLEAR_PLAYLIST)

    @property
    def support_shuffle_set(self):
        """Boolean if shuffle is supported."""
        return bool(self.supported_features & SUPPORT_SHUFFLE_SET)

    async def async_toggle(self):
        """Toggle the power on the media player."""
        if hasattr(self, "toggle"):
            # pylint: disable=no-member
            await self.hass.async_add_job(self.toggle)
            return

        if self.state in [STATE_OFF, STATE_IDLE]:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    async def async_volume_up(self):
        """Turn volume up for media player.

        This method is a coroutine.
        """
        if hasattr(self, "volume_up"):
            # pylint: disable=no-member
            await self.hass.async_add_job(self.volume_up)
            return

        if self.volume_level < 1 and self.supported_features & SUPPORT_VOLUME_SET:
            await self.async_set_volume_level(min(1, self.volume_level + 0.1))

    async def async_volume_down(self):
        """Turn volume down for media player.

        This method is a coroutine.
        """
        if hasattr(self, "volume_down"):
            # pylint: disable=no-member
            await self.hass.async_add_job(self.volume_down)
            return

        if self.volume_level > 0 and self.supported_features & SUPPORT_VOLUME_SET:
            await self.async_set_volume_level(max(0, self.volume_level - 0.1))

    async def async_media_play_pause(self):
        """Play or pause the media player."""
        if hasattr(self, "media_play_pause"):
            # pylint: disable=no-member
            await self.hass.async_add_job(self.media_play_pause)
            return

        if self.state == STATE_PLAYING:
            await self.async_media_pause()
        else:
            await self.async_media_play()

    @property
    def entity_picture(self):
        """Return image of the media playing."""
        if self.state == STATE_OFF:
            return None

        if self.media_image_remotely_accessible:
            return self.media_image_url

        return self.media_image_local

    @property
    def media_image_local(self):
        """Return local url to media image."""
        image_hash = self.media_image_hash

        if image_hash is None:
            return None

        return (
            f"/api/media_player_proxy/{self.entity_id}?"
            f"token={self.access_token}&cache={image_hash}"
        )

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        supported_features = self.supported_features or 0
        data = {}

        if supported_features & SUPPORT_SELECT_SOURCE:
            source_list = self.source_list
            if source_list:
                data[ATTR_INPUT_SOURCE_LIST] = source_list

        if supported_features & SUPPORT_SELECT_SOUND_MODE:
            sound_mode_list = self.sound_mode_list
            if sound_mode_list:
                data[ATTR_SOUND_MODE_LIST] = sound_mode_list

        return data

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.state == STATE_OFF:
            return None

        state_attr = {}

        for attr in ATTR_TO_PROPERTY:
            value = getattr(self, attr)
            if value is not None:
                state_attr[attr] = value

        if self.media_image_remotely_accessible:
            state_attr["entity_picture_local"] = self.media_image_local

        return state_attr


async def _async_fetch_image(hass, url):
    """Fetch image.

    Images are cached in memory (the images are typically 10-100kB in size).
    """
    cache_images = ENTITY_IMAGE_CACHE[CACHE_IMAGES]
    cache_maxsize = ENTITY_IMAGE_CACHE[CACHE_MAXSIZE]

    if urlparse(url).hostname is None:
        url = f"{get_url(hass)}{url}"

    if url not in cache_images:
        cache_images[url] = {CACHE_LOCK: asyncio.Lock()}

    async with cache_images[url][CACHE_LOCK]:
        if CACHE_CONTENT in cache_images[url]:
            return cache_images[url][CACHE_CONTENT]

        content, content_type = (None, None)
        websession = async_get_clientsession(hass)
        try:
            with async_timeout.timeout(10):
                response = await websession.get(url)

                if response.status == HTTP_OK:
                    content = await response.read()
                    content_type = response.headers.get(CONTENT_TYPE)
                    if content_type:
                        content_type = content_type.split(";")[0]
                    cache_images[url][CACHE_CONTENT] = content, content_type

        except asyncio.TimeoutError:
            pass

        while len(cache_images) > cache_maxsize:
            cache_images.popitem(last=False)

        return content, content_type


class MediaPlayerImageView(HomeAssistantView):
    """Media player view to serve an image."""

    requires_auth = False
    url = "/api/media_player_proxy/{entity_id}"
    name = "api:media_player:image"

    def __init__(self, component):
        """Initialize a media player view."""
        self.component = component

    async def get(self, request: web.Request, entity_id: str) -> web.Response:
        """Start a get request."""
        player = self.component.get_entity(entity_id)
        if player is None:
            status = HTTP_NOT_FOUND if request[KEY_AUTHENTICATED] else 401
            return web.Response(status=status)

        authenticated = (
            request[KEY_AUTHENTICATED]
            or request.query.get("token") == player.access_token
        )

        if not authenticated:
            return web.Response(status=401)

        data, content_type = await player.async_get_media_image()

        if data is None:
            return web.Response(status=HTTP_INTERNAL_SERVER_ERROR)

        headers: LooseHeaders = {CACHE_CONTROL: "max-age=3600"}
        return web.Response(body=data, content_type=content_type, headers=headers)


@websocket_api.async_response
async def websocket_handle_thumbnail(hass, connection, msg):
    """Handle get media player cover command.

    Async friendly.
    """
    component = hass.data[DOMAIN]
    player = component.get_entity(msg["entity_id"])

    if player is None:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "entity_not_found", "Entity not found"
            )
        )
        return

    _LOGGER.warning(
        "The websocket command media_player_thumbnail is deprecated. Use /api/media_player_proxy instead."
    )

    data, content_type = await player.async_get_media_image()

    if data is None:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "thumbnail_fetch_failed", "Failed to fetch thumbnail"
            )
        )
        return

    await connection.send_big_result(
        msg["id"],
        {
            "content_type": content_type,
            "content": base64.b64encode(data).decode("utf-8"),
        },
    )


class MediaPlayerDevice(MediaPlayerEntity):
    """ABC for media player devices (for backwards compatibility)."""

    def __init_subclass__(cls, **kwargs):
        """Print deprecation warning."""
        super().__init_subclass__(**kwargs)
        _LOGGER.warning(
            "MediaPlayerDevice is deprecated, modify %s to extend MediaPlayerEntity",
            cls.__name__,
        )
