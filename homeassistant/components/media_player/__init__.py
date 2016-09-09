"""
Component to interface with various media players.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/media_player/
"""
import hashlib
import logging
import os
import requests

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.components.http import HomeAssistantView
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    STATE_OFF, STATE_UNKNOWN, STATE_PLAYING, STATE_IDLE,
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_VOLUME_UP, SERVICE_VOLUME_DOWN, SERVICE_VOLUME_SET,
    SERVICE_VOLUME_MUTE, SERVICE_TOGGLE, SERVICE_MEDIA_STOP,
    SERVICE_MEDIA_PLAY_PAUSE, SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_MEDIA_SEEK)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'media_player'
DEPENDENCIES = ['http']
SCAN_INTERVAL = 10

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ENTITY_IMAGE_URL = '/api/media_player_proxy/{0}?token={1}&cache={2}'

SERVICE_PLAY_MEDIA = 'play_media'
SERVICE_SELECT_SOURCE = 'select_source'
SERVICE_CLEAR_PLAYLIST = 'clear_playlist'

ATTR_MEDIA_VOLUME_LEVEL = 'volume_level'
ATTR_MEDIA_VOLUME_MUTED = 'is_volume_muted'
ATTR_MEDIA_SEEK_POSITION = 'seek_position'
ATTR_MEDIA_CONTENT_ID = 'media_content_id'
ATTR_MEDIA_CONTENT_TYPE = 'media_content_type'
ATTR_MEDIA_DURATION = 'media_duration'
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
ATTR_SUPPORTED_MEDIA_COMMANDS = 'supported_media_commands'
ATTR_INPUT_SOURCE = 'source'
ATTR_INPUT_SOURCE_LIST = 'source_list'
ATTR_MEDIA_ENQUEUE = 'enqueue'

MEDIA_TYPE_MUSIC = 'music'
MEDIA_TYPE_TVSHOW = 'tvshow'
MEDIA_TYPE_VIDEO = 'movie'
MEDIA_TYPE_EPISODE = 'episode'
MEDIA_TYPE_CHANNEL = 'channel'
MEDIA_TYPE_PLAYLIST = 'playlist'

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

# simple services that only take entity_id(s) as optional argument
SERVICE_TO_METHOD = {
    SERVICE_TURN_ON: 'turn_on',
    SERVICE_TURN_OFF: 'turn_off',
    SERVICE_TOGGLE: 'toggle',
    SERVICE_VOLUME_UP: 'volume_up',
    SERVICE_VOLUME_DOWN: 'volume_down',
    SERVICE_MEDIA_PLAY_PAUSE: 'media_play_pause',
    SERVICE_MEDIA_PLAY: 'media_play',
    SERVICE_MEDIA_PAUSE: 'media_pause',
    SERVICE_MEDIA_STOP: 'media_stop',
    SERVICE_MEDIA_NEXT_TRACK: 'media_next_track',
    SERVICE_MEDIA_PREVIOUS_TRACK: 'media_previous_track',
    SERVICE_CLEAR_PLAYLIST: 'clear_playlist'
}

ATTR_TO_PROPERTY = [
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
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
    ATTR_SUPPORTED_MEDIA_COMMANDS,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
]

# Service call validation schemas
MEDIA_PLAYER_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
})

MEDIA_PLAYER_MUTE_VOLUME_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_VOLUME_MUTED): cv.boolean,
})

MEDIA_PLAYER_SET_VOLUME_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_VOLUME_LEVEL): cv.small_float,
})

MEDIA_PLAYER_MEDIA_SEEK_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_SEEK_POSITION):
        vol.All(vol.Coerce(float), vol.Range(min=0)),
})

MEDIA_PLAYER_PLAY_MEDIA_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_CONTENT_TYPE): cv.string,
    vol.Required(ATTR_MEDIA_CONTENT_ID): cv.string,
    ATTR_MEDIA_ENQUEUE: cv.boolean,
})

MEDIA_PLAYER_SELECT_SOURCE_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_INPUT_SOURCE): cv.string,
})


def is_on(hass, entity_id=None):
    """
    Return true if specified media player entity_id is on.

    Check all media player if no entity_id specified.
    """
    entity_ids = [entity_id] if entity_id else hass.states.entity_ids(DOMAIN)
    return any(not hass.states.is_state(entity_id, STATE_OFF)
               for entity_id in entity_ids)


def turn_on(hass, entity_id=None):
    """Turn on specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None):
    """Turn off specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


def toggle(hass, entity_id=None):
    """Toggle specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


def volume_up(hass, entity_id=None):
    """Send the media player the command for volume up."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_VOLUME_UP, data)


def volume_down(hass, entity_id=None):
    """Send the media player the command for volume down."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_VOLUME_DOWN, data)


def mute_volume(hass, mute, entity_id=None):
    """Send the media player the command for muting the volume."""
    data = {ATTR_MEDIA_VOLUME_MUTED: mute}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_VOLUME_MUTE, data)


def set_volume_level(hass, volume, entity_id=None):
    """Send the media player the command for setting the volume."""
    data = {ATTR_MEDIA_VOLUME_LEVEL: volume}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_VOLUME_SET, data)


def media_play_pause(hass, entity_id=None):
    """Send the media player the command for play/pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, data)


def media_play(hass, entity_id=None):
    """Send the media player the command for play/pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_PLAY, data)


def media_pause(hass, entity_id=None):
    """Send the media player the command for pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_PAUSE, data)


def media_stop(hass, entity_id=None):
    """Send the media player the stop command."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_STOP, data)


def media_next_track(hass, entity_id=None):
    """Send the media player the command for next track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_NEXT_TRACK, data)


def media_previous_track(hass, entity_id=None):
    """Send the media player the command for prev track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, data)


def media_seek(hass, position, entity_id=None):
    """Send the media player the command to seek in current playing media."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_MEDIA_SEEK_POSITION] = position
    hass.services.call(DOMAIN, SERVICE_MEDIA_SEEK, data)


def play_media(hass, media_type, media_id, entity_id=None, enqueue=None):
    """Send the media player the command for playing media."""
    data = {ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if enqueue:
        data[ATTR_MEDIA_ENQUEUE] = enqueue

    hass.services.call(DOMAIN, SERVICE_PLAY_MEDIA, data)


def select_source(hass, source, entity_id=None):
    """Send the media player the command to select input source."""
    data = {ATTR_INPUT_SOURCE: source}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SELECT_SOURCE, data)


def clear_playlist(hass, entity_id=None):
    """Send the media player the command for clear playlist."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_CLEAR_PLAYLIST, data)


def setup(hass, config):
    """Track states and offer events for media_players."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)

    hass.wsgi.register_view(MediaPlayerImageView(hass, component.entities))

    component.setup(config)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def media_player_service_handler(service):
        """Map services to methods on MediaPlayerDevice."""
        method = SERVICE_TO_METHOD[service.service]

        for player in component.extract_from_service(service):
            getattr(player, method)()

            if player.should_poll:
                player.update_ha_state(True)

    for service in SERVICE_TO_METHOD:
        hass.services.register(DOMAIN, service, media_player_service_handler,
                               descriptions.get(service),
                               schema=MEDIA_PLAYER_SCHEMA)

    def volume_set_service(service):
        """Set specified volume on the media player."""
        volume = service.data.get(ATTR_MEDIA_VOLUME_LEVEL)

        for player in component.extract_from_service(service):
            player.set_volume_level(volume)

            if player.should_poll:
                player.update_ha_state(True)

    hass.services.register(DOMAIN, SERVICE_VOLUME_SET, volume_set_service,
                           descriptions.get(SERVICE_VOLUME_SET),
                           schema=MEDIA_PLAYER_SET_VOLUME_SCHEMA)

    def volume_mute_service(service):
        """Mute (true) or unmute (false) the media player."""
        mute = service.data.get(ATTR_MEDIA_VOLUME_MUTED)

        for player in component.extract_from_service(service):
            player.mute_volume(mute)

            if player.should_poll:
                player.update_ha_state(True)

    hass.services.register(DOMAIN, SERVICE_VOLUME_MUTE, volume_mute_service,
                           descriptions.get(SERVICE_VOLUME_MUTE),
                           schema=MEDIA_PLAYER_MUTE_VOLUME_SCHEMA)

    def media_seek_service(service):
        """Seek to a position."""
        position = service.data.get(ATTR_MEDIA_SEEK_POSITION)

        for player in component.extract_from_service(service):
            player.media_seek(position)

            if player.should_poll:
                player.update_ha_state(True)

    hass.services.register(DOMAIN, SERVICE_MEDIA_SEEK, media_seek_service,
                           descriptions.get(SERVICE_MEDIA_SEEK),
                           schema=MEDIA_PLAYER_MEDIA_SEEK_SCHEMA)

    def select_source_service(service):
        """Change input to selected source."""
        input_source = service.data.get(ATTR_INPUT_SOURCE)

        for player in component.extract_from_service(service):
            player.select_source(input_source)

            if player.should_poll:
                player.update_ha_state(True)

    hass.services.register(DOMAIN, SERVICE_SELECT_SOURCE,
                           select_source_service,
                           descriptions.get(SERVICE_SELECT_SOURCE),
                           schema=MEDIA_PLAYER_SELECT_SOURCE_SCHEMA)

    def play_media_service(service):
        """Play specified media_id on the media player."""
        media_type = service.data.get(ATTR_MEDIA_CONTENT_TYPE)
        media_id = service.data.get(ATTR_MEDIA_CONTENT_ID)
        enqueue = service.data.get(ATTR_MEDIA_ENQUEUE)

        kwargs = {
            ATTR_MEDIA_ENQUEUE: enqueue,
        }

        for player in component.extract_from_service(service):
            player.play_media(media_type, media_id, **kwargs)

            if player.should_poll:
                player.update_ha_state(True)

    hass.services.register(DOMAIN, SERVICE_PLAY_MEDIA, play_media_service,
                           descriptions.get(SERVICE_PLAY_MEDIA),
                           schema=MEDIA_PLAYER_PLAY_MEDIA_SCHEMA)

    return True


class MediaPlayerDevice(Entity):
    """ABC for media player devices."""

    # pylint: disable=too-many-public-methods,no-self-use

    # Implement these for your media player

    @property
    def state(self):
        """State of the player."""
        return STATE_UNKNOWN

    @property
    def access_token(self):
        """Access token for this media player."""
        return str(id(self))

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
    def media_image_url(self):
        """Image url of current playing media."""
        return None

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
    def supported_media_commands(self):
        """Flag media commands that are supported."""
        return 0

    def turn_on(self):
        """Turn the media player on."""
        raise NotImplementedError()

    def turn_off(self):
        """Turn the media player off."""
        raise NotImplementedError()

    def mute_volume(self, mute):
        """Mute the volume."""
        raise NotImplementedError()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        raise NotImplementedError()

    def media_play(self):
        """Send play commmand."""
        raise NotImplementedError()

    def media_pause(self):
        """Send pause command."""
        raise NotImplementedError()

    def media_stop(self):
        """Send stop command."""
        raise NotImplementedError()

    def media_previous_track(self):
        """Send previous track command."""
        raise NotImplementedError()

    def media_next_track(self):
        """Send next track command."""
        raise NotImplementedError()

    def media_seek(self, position):
        """Send seek command."""
        raise NotImplementedError()

    def play_media(self, media_type, media_id):
        """Play a piece of media."""
        raise NotImplementedError()

    def select_source(self, source):
        """Select input source."""
        raise NotImplementedError()

    def clear_playlist(self):
        """Clear players playlist."""
        raise NotImplementedError()

    # No need to overwrite these.
    @property
    def support_pause(self):
        """Boolean if pause is supported."""
        return bool(self.supported_media_commands & SUPPORT_PAUSE)

    @property
    def support_stop(self):
        """Boolean if stop is supported."""
        return bool(self.supported_media_commands & SUPPORT_STOP)

    @property
    def support_seek(self):
        """Boolean if seek is supported."""
        return bool(self.supported_media_commands & SUPPORT_SEEK)

    @property
    def support_volume_set(self):
        """Boolean if setting volume is supported."""
        return bool(self.supported_media_commands & SUPPORT_VOLUME_SET)

    @property
    def support_volume_mute(self):
        """Boolean if muting volume is supported."""
        return bool(self.supported_media_commands & SUPPORT_VOLUME_MUTE)

    @property
    def support_previous_track(self):
        """Boolean if previous track command supported."""
        return bool(self.supported_media_commands & SUPPORT_PREVIOUS_TRACK)

    @property
    def support_next_track(self):
        """Boolean if next track command supported."""
        return bool(self.supported_media_commands & SUPPORT_NEXT_TRACK)

    @property
    def support_play_media(self):
        """Boolean if play media command supported."""
        return bool(self.supported_media_commands & SUPPORT_PLAY_MEDIA)

    @property
    def support_select_source(self):
        """Boolean if select source command supported."""
        return bool(self.supported_media_commands & SUPPORT_SELECT_SOURCE)

    @property
    def support_clear_playlist(self):
        """Boolean if clear playlist command supported."""
        return bool(self.supported_media_commands & SUPPORT_CLEAR_PLAYLIST)

    def toggle(self):
        """Toggle the power on the media player."""
        if self.state in [STATE_OFF, STATE_IDLE]:
            self.turn_on()
        else:
            self.turn_off()

    def volume_up(self):
        """Turn volume up for media player."""
        if self.volume_level < 1:
            self.set_volume_level(min(1, self.volume_level + .1))

    def volume_down(self):
        """Turn volume down for media player."""
        if self.volume_level > 0:
            self.set_volume_level(max(0, self.volume_level - .1))

    def media_play_pause(self):
        """Play or pause the media player."""
        if self.state == STATE_PLAYING:
            self.media_pause()
        else:
            self.media_play()

    @property
    def entity_picture(self):
        """Return image of the media playing."""
        if self.state == STATE_OFF:
            return None

        url = self.media_image_url

        if url is None:
            return None

        return ENTITY_IMAGE_URL.format(
            self.entity_id, self.access_token,
            hashlib.md5(url.encode('utf-8')).hexdigest()[:5])

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.state == STATE_OFF:
            state_attr = {
                ATTR_SUPPORTED_MEDIA_COMMANDS: self.supported_media_commands,
            }
        else:
            state_attr = {
                attr: getattr(self, attr) for attr
                in ATTR_TO_PROPERTY if getattr(self, attr) is not None
            }

        return state_attr


class MediaPlayerImageView(HomeAssistantView):
    """Media player view to serve an image."""

    requires_auth = False
    url = "/api/media_player_proxy/<entity(domain=media_player):entity_id>"
    name = "api:media_player:image"

    def __init__(self, hass, entities):
        """Initialize a media player view."""
        super().__init__(hass)
        self.entities = entities

    def get(self, request, entity_id):
        """Start a get request."""
        player = self.entities.get(entity_id)

        if player is None:
            return self.Response(status=404)

        authenticated = (request.authenticated or
                         request.args.get('token') == player.access_token)

        if not authenticated:
            return self.Response(status=401)

        image_url = player.media_image_url
        if image_url:
            response = requests.get(image_url)
        else:
            response = None

        if response is None:
            return self.Response(status=500)

        return self.Response(response)
