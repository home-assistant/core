"""
Component to interface with various media players.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/media_player/
"""
import asyncio
import base64
import collections
from datetime import timedelta
import functools as ft
import hashlib
import logging
from random import SystemRandom
from urllib.parse import urlparse

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL, CONTENT_TYPE
import async_timeout
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PLAY_PAUSE, SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK, SERVICE_MEDIA_STOP, SERVICE_SHUFFLE_SET,
    SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE, SERVICE_VOLUME_SET, SERVICE_VOLUME_UP, STATE_IDLE,
    STATE_OFF, STATE_PLAYING, STATE_UNKNOWN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)
_RND = SystemRandom()

DOMAIN = 'media_player'
DEPENDENCIES = ['http']

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ENTITY_IMAGE_URL = '/api/media_player_proxy/{0}?token={1}&cache={2}'
CACHE_IMAGES = 'images'
CACHE_MAXSIZE = 'maxsize'
CACHE_LOCK = 'lock'
CACHE_URL = 'url'
CACHE_CONTENT = 'content'
ENTITY_IMAGE_CACHE = {
    CACHE_IMAGES: collections.OrderedDict(),
    CACHE_MAXSIZE: 16
}

SERVICE_PLAY_MEDIA = 'play_media'
SERVICE_SELECT_SOURCE = 'select_source'
SERVICE_SELECT_SOUND_MODE = 'select_sound_mode'
SERVICE_CLEAR_PLAYLIST = 'clear_playlist'

ATTR_MEDIA_VOLUME_LEVEL = 'volume_level'
ATTR_MEDIA_VOLUME_MUTED = 'is_volume_muted'
ATTR_MEDIA_SEEK_POSITION = 'seek_position'
ATTR_MEDIA_CONTENT_ID = 'media_content_id'
ATTR_MEDIA_CONTENT_TYPE = 'media_content_type'
ATTR_MEDIA_DURATION = 'media_duration'
ATTR_MEDIA_POSITION = 'media_position'
ATTR_MEDIA_POSITION_UPDATED_AT = 'media_position_updated_at'
ATTR_MEDIA_TITLE = 'media_title'
ATTR_MEDIA_ARTIST = 'media_artist'
ATTR_MEDIA_ALBUM_NAME = 'media_album_name'
ATTR_MEDIA_ALBUM_ARTIST = 'media_album_artist'
ATTR_MEDIA_TRACK = 'media_track'
ATTR_MEDIA_SERIES_TITLE = 'media_series_title'
ATTR_MEDIA_SEASON = 'media_season'
ATTR_MEDIA_EPISODE = 'media_episode'
ATTR_MEDIA_CHANNEL = 'media_channel'
ATTR_MEDIA_PLAYLIST = 'media_playlist'
ATTR_APP_ID = 'app_id'
ATTR_APP_NAME = 'app_name'
ATTR_INPUT_SOURCE = 'source'
ATTR_INPUT_SOURCE_LIST = 'source_list'
ATTR_SOUND_MODE = 'sound_mode'
ATTR_SOUND_MODE_LIST = 'sound_mode_list'
ATTR_MEDIA_ENQUEUE = 'enqueue'
ATTR_MEDIA_SHUFFLE = 'shuffle'

MEDIA_TYPE_MUSIC = 'music'
MEDIA_TYPE_TVSHOW = 'tvshow'
MEDIA_TYPE_MOVIE = 'movie'
MEDIA_TYPE_VIDEO = 'video'
MEDIA_TYPE_EPISODE = 'episode'
MEDIA_TYPE_CHANNEL = 'channel'
MEDIA_TYPE_PLAYLIST = 'playlist'
MEDIA_TYPE_URL = 'url'

SCAN_INTERVAL = timedelta(seconds=10)

SUPPORT_PAUSE = 1
SUPPORT_SEEK = 2
SUPPORT_VOLUME_SET = 4
SUPPORT_VOLUME_MUTE = 8
SUPPORT_PREVIOUS_TRACK = 16
SUPPORT_NEXT_TRACK = 32

SUPPORT_TURN_ON = 128
SUPPORT_TURN_OFF = 256
SUPPORT_PLAY_MEDIA = 512
SUPPORT_VOLUME_STEP = 1024
SUPPORT_SELECT_SOURCE = 2048
SUPPORT_STOP = 4096
SUPPORT_CLEAR_PLAYLIST = 8192
SUPPORT_PLAY = 16384
SUPPORT_SHUFFLE_SET = 32768
SUPPORT_SELECT_SOUND_MODE = 65536

# Service call validation schemas
MEDIA_PLAYER_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
})

MEDIA_PLAYER_SET_VOLUME_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_VOLUME_LEVEL): cv.small_float,
})

MEDIA_PLAYER_MUTE_VOLUME_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_VOLUME_MUTED): cv.boolean,
})

MEDIA_PLAYER_MEDIA_SEEK_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_SEEK_POSITION):
        vol.All(vol.Coerce(float), vol.Range(min=0)),
})

MEDIA_PLAYER_SELECT_SOURCE_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_INPUT_SOURCE): cv.string,
})

MEDIA_PLAYER_SELECT_SOUND_MODE_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_SOUND_MODE): cv.string,
})

MEDIA_PLAYER_PLAY_MEDIA_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_CONTENT_TYPE): cv.string,
    vol.Required(ATTR_MEDIA_CONTENT_ID): cv.string,
    vol.Optional(ATTR_MEDIA_ENQUEUE): cv.boolean,
})

MEDIA_PLAYER_SET_SHUFFLE_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_SHUFFLE): cv.boolean,
})

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
    ATTR_INPUT_SOURCE_LIST,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    ATTR_MEDIA_SHUFFLE,
]


@bind_hass
def is_on(hass, entity_id=None):
    """
    Return true if specified media player entity_id is on.

    Check all media player if no entity_id specified.
    """
    entity_ids = [entity_id] if entity_id else hass.states.entity_ids(DOMAIN)
    return any(not hass.states.is_state(entity_id, STATE_OFF)
               for entity_id in entity_ids)


WS_TYPE_MEDIA_PLAYER_THUMBNAIL = 'media_player_thumbnail'
SCHEMA_WEBSOCKET_GET_THUMBNAIL = \
    websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
        'type': WS_TYPE_MEDIA_PLAYER_THUMBNAIL,
        'entity_id': cv.entity_id
    })


async def async_setup(hass, config):
    """Track states and offer events for media_players."""
    component = hass.data[DOMAIN] = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_MEDIA_PLAYER_THUMBNAIL, websocket_handle_thumbnail,
        SCHEMA_WEBSOCKET_GET_THUMBNAIL)
    hass.http.register_view(MediaPlayerImageView(component))

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON, MEDIA_PLAYER_SCHEMA,
        'async_turn_on'
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, MEDIA_PLAYER_SCHEMA,
        'async_turn_off'
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE, MEDIA_PLAYER_SCHEMA,
        'async_toggle'
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_UP, MEDIA_PLAYER_SCHEMA,
        'async_volume_up'
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_DOWN, MEDIA_PLAYER_SCHEMA,
        'async_volume_down'
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PLAY_PAUSE, MEDIA_PLAYER_SCHEMA,
        'async_media_play_pause'
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PLAY, MEDIA_PLAYER_SCHEMA,
        'async_media_play'
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PAUSE, MEDIA_PLAYER_SCHEMA,
        'async_media_pause'
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_STOP, MEDIA_PLAYER_SCHEMA,
        'async_media_stop'
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_NEXT_TRACK, MEDIA_PLAYER_SCHEMA,
        'async_media_next_track'
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PREVIOUS_TRACK, MEDIA_PLAYER_SCHEMA,
        'async_media_previous_track'
    )
    component.async_register_entity_service(
        SERVICE_CLEAR_PLAYLIST, MEDIA_PLAYER_SCHEMA,
        'async_clear_playlist'
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_SET, MEDIA_PLAYER_SET_VOLUME_SCHEMA,
        lambda entity, call: entity.async_set_volume_level(
            volume=call.data[ATTR_MEDIA_VOLUME_LEVEL])
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_MUTE, MEDIA_PLAYER_MUTE_VOLUME_SCHEMA,
        lambda entity, call: entity.async_mute_volume(
            mute=call.data[ATTR_MEDIA_VOLUME_MUTED])
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_SEEK, MEDIA_PLAYER_MEDIA_SEEK_SCHEMA,
        lambda entity, call: entity.async_media_seek(
            position=call.data[ATTR_MEDIA_SEEK_POSITION])
    )
    component.async_register_entity_service(
        SERVICE_SELECT_SOURCE, MEDIA_PLAYER_SELECT_SOURCE_SCHEMA,
        'async_select_source'
    )
    component.async_register_entity_service(
        SERVICE_SELECT_SOUND_MODE, MEDIA_PLAYER_SELECT_SOUND_MODE_SCHEMA,
        'async_select_sound_mode'
    )
    component.async_register_entity_service(
        SERVICE_PLAY_MEDIA, MEDIA_PLAYER_PLAY_MEDIA_SCHEMA,
        lambda entity, call: entity.async_play_media(
            media_type=call.data[ATTR_MEDIA_CONTENT_TYPE],
            media_id=call.data[ATTR_MEDIA_CONTENT_ID],
            enqueue=call.data.get(ATTR_MEDIA_ENQUEUE)
        )
    )
    component.async_register_entity_service(
        SERVICE_SHUFFLE_SET, MEDIA_PLAYER_SET_SHUFFLE_SCHEMA,
        'async_set_shuffle'
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class MediaPlayerDevice(Entity):
    """ABC for media player devices."""

    _access_token = None

    # Implement these for your media player
    @property
    def state(self):
        """State of the player."""
        return STATE_UNKNOWN

    @property
    def access_token(self):
        """Access token for this media player."""
        if self._access_token is None:
            self._access_token = hashlib.sha256(
                _RND.getrandbits(256).to_bytes(32, 'little')).hexdigest()
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
    def media_image_hash(self):
        """Hash value for media image."""
        url = self.media_image_url
        if url is not None:
            return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]

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

    def async_turn_on(self):
        """Turn the media player on.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_on)

    def turn_off(self):
        """Turn the media player off."""
        raise NotImplementedError()

    def async_turn_off(self):
        """Turn the media player off.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_off)

    def mute_volume(self, mute):
        """Mute the volume."""
        raise NotImplementedError()

    def async_mute_volume(self, mute):
        """Mute the volume.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.mute_volume, mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        raise NotImplementedError()

    def async_set_volume_level(self, volume):
        """Set volume level, range 0..1.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_volume_level, volume)

    def media_play(self):
        """Send play command."""
        raise NotImplementedError()

    def async_media_play(self):
        """Send play command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.media_play)

    def media_pause(self):
        """Send pause command."""
        raise NotImplementedError()

    def async_media_pause(self):
        """Send pause command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.media_pause)

    def media_stop(self):
        """Send stop command."""
        raise NotImplementedError()

    def async_media_stop(self):
        """Send stop command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.media_stop)

    def media_previous_track(self):
        """Send previous track command."""
        raise NotImplementedError()

    def async_media_previous_track(self):
        """Send previous track command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.media_previous_track)

    def media_next_track(self):
        """Send next track command."""
        raise NotImplementedError()

    def async_media_next_track(self):
        """Send next track command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.media_next_track)

    def media_seek(self, position):
        """Send seek command."""
        raise NotImplementedError()

    def async_media_seek(self, position):
        """Send seek command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.media_seek, position)

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        raise NotImplementedError()

    def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.play_media, media_type, media_id, **kwargs))

    def select_source(self, source):
        """Select input source."""
        raise NotImplementedError()

    def async_select_source(self, source):
        """Select input source.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.select_source, source)

    def select_sound_mode(self, sound_mode):
        """Select sound mode."""
        raise NotImplementedError()

    def async_select_sound_mode(self, sound_mode):
        """Select sound mode.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.select_sound_mode, sound_mode)

    def clear_playlist(self):
        """Clear players playlist."""
        raise NotImplementedError()

    def async_clear_playlist(self):
        """Clear players playlist.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.clear_playlist)

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        raise NotImplementedError()

    def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_shuffle, shuffle)

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

    def async_toggle(self):
        """Toggle the power on the media player.

        This method must be run in the event loop and returns a coroutine.
        """
        if hasattr(self, 'toggle'):
            # pylint: disable=no-member
            return self.hass.async_add_job(self.toggle)

        if self.state in [STATE_OFF, STATE_IDLE]:
            return self.async_turn_on()
        return self.async_turn_off()

    async def async_volume_up(self):
        """Turn volume up for media player.

        This method is a coroutine.
        """
        if hasattr(self, 'volume_up'):
            # pylint: disable=no-member
            await self.hass.async_add_job(self.volume_up)
            return

        if self.volume_level < 1:
            await self.async_set_volume_level(min(1, self.volume_level + .1))

    async def async_volume_down(self):
        """Turn volume down for media player.

        This method is a coroutine.
        """
        if hasattr(self, 'volume_down'):
            # pylint: disable=no-member
            await self.hass.async_add_job(self.volume_down)
            return

        if self.volume_level > 0:
            await self.async_set_volume_level(
                max(0, self.volume_level - .1))

    def async_media_play_pause(self):
        """Play or pause the media player.

        This method must be run in the event loop and returns a coroutine.
        """
        if hasattr(self, 'media_play_pause'):
            # pylint: disable=no-member
            return self.hass.async_add_job(self.media_play_pause)

        if self.state == STATE_PLAYING:
            return self.async_media_pause()
        return self.async_media_play()

    @property
    def entity_picture(self):
        """Return image of the media playing."""
        if self.state == STATE_OFF:
            return None

        image_hash = self.media_image_hash

        if image_hash is None:
            return None

        return ENTITY_IMAGE_URL.format(
            self.entity_id, self.access_token, image_hash)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.state == STATE_OFF:
            return None

        state_attr = {
            attr: getattr(self, attr) for attr
            in ATTR_TO_PROPERTY if getattr(self, attr) is not None
        }

        return state_attr


async def _async_fetch_image(hass, url):
    """Fetch image.

    Images are cached in memory (the images are typically 10-100kB in size).
    """
    cache_images = ENTITY_IMAGE_CACHE[CACHE_IMAGES]
    cache_maxsize = ENTITY_IMAGE_CACHE[CACHE_MAXSIZE]

    if urlparse(url).hostname is None:
        url = hass.config.api.base_url + url

    if url not in cache_images:
        cache_images[url] = {CACHE_LOCK: asyncio.Lock(loop=hass.loop)}

    async with cache_images[url][CACHE_LOCK]:
        if CACHE_CONTENT in cache_images[url]:
            return cache_images[url][CACHE_CONTENT]

        content, content_type = (None, None)
        websession = async_get_clientsession(hass)
        try:
            with async_timeout.timeout(10, loop=hass.loop):
                response = await websession.get(url)

                if response.status == 200:
                    content = await response.read()
                    content_type = response.headers.get(CONTENT_TYPE)
                    if content_type:
                        content_type = content_type.split(';')[0]
                    cache_images[url][CACHE_CONTENT] = content, content_type

        except asyncio.TimeoutError:
            pass

        while len(cache_images) > cache_maxsize:
            cache_images.popitem(last=False)

        return content, content_type


class MediaPlayerImageView(HomeAssistantView):
    """Media player view to serve an image."""

    requires_auth = False
    url = '/api/media_player_proxy/{entity_id}'
    name = 'api:media_player:image'

    def __init__(self, component):
        """Initialize a media player view."""
        self.component = component

    async def get(self, request, entity_id):
        """Start a get request."""
        player = self.component.get_entity(entity_id)
        if player is None:
            status = 404 if request[KEY_AUTHENTICATED] else 401
            return web.Response(status=status)

        authenticated = (request[KEY_AUTHENTICATED] or
                         request.query.get('token') == player.access_token)

        if not authenticated:
            return web.Response(status=401)

        data, content_type = await player.async_get_media_image()

        if data is None:
            return web.Response(status=500)

        headers = {CACHE_CONTROL: 'max-age=3600'}
        return web.Response(
            body=data, content_type=content_type, headers=headers)


@websocket_api.async_response
async def websocket_handle_thumbnail(hass, connection, msg):
    """Handle get media player cover command.

    Async friendly.
    """
    component = hass.data[DOMAIN]
    player = component.get_entity(msg['entity_id'])

    if player is None:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'entity_not_found', 'Entity not found'))
        return

    data, content_type = await player.async_get_media_image()

    if data is None:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'thumbnail_fetch_failed',
            'Failed to fetch thumbnail'))
        return

    connection.send_message(websocket_api.result_message(
        msg['id'], {
            'content_type': content_type,
            'content': base64.b64encode(data).decode('utf-8')
        }))
