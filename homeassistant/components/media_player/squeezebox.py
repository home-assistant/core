"""
Support for interfacing to the Logitech SqueezeBox API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.squeezebox/
"""
import logging
import asyncio
import urllib.parse
import json
import aiohttp
import async_timeout

import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE, SUPPORT_PLAY_MEDIA,
    MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, PLATFORM_SCHEMA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_PLAY, MediaPlayerDevice,
    MEDIA_PLAYER_SCHEMA, DOMAIN, SUPPORT_SHUFFLE_SET, SUPPORT_CLEAR_PLAYLIST)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_IDLE, STATE_OFF,
    STATE_PAUSED, STATE_PLAYING, STATE_UNKNOWN, CONF_PORT, ATTR_COMMAND)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 9000
TIMEOUT = 10

SUPPORT_SQUEEZEBOX = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | \
    SUPPORT_VOLUME_MUTE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_SEEK | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PLAY_MEDIA | \
    SUPPORT_PLAY | SUPPORT_SHUFFLE_SET | SUPPORT_CLEAR_PLAYLIST

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_USERNAME): cv.string,
})

SERVICE_CALL_METHOD = 'squeezebox_call_method'

DATA_SQUEEZEBOX = 'squeexebox'

ATTR_PARAMETERS = 'parameters'

SQUEEZEBOX_CALL_METHOD_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PARAMETERS):
        vol.All(cv.ensure_list, vol.Length(min=1), [cv.string]),
})

SERVICE_TO_METHOD = {
    SERVICE_CALL_METHOD: {
        'method': 'async_call_method',
        'schema': SQUEEZEBOX_CALL_METHOD_SCHEMA},
}


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the squeezebox platform."""
    import socket

    if DATA_SQUEEZEBOX not in hass.data:
        hass.data[DATA_SQUEEZEBOX] = []

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if discovery_info is not None:
        host = discovery_info.get("host")
        port = discovery_info.get("port")
    else:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)

    # In case the port is not discovered
    if port is None:
        port = DEFAULT_PORT

    # Get IP of host, to prevent duplication of same host (different DNS names)
    try:
        ipaddr = socket.gethostbyname(host)
    except (OSError) as error:
        _LOGGER.error(
            "Could not communicate with %s:%d: %s", host, port, error)
        return False

    _LOGGER.debug("Creating LMS object for %s", ipaddr)
    lms = LogitechMediaServer(hass, host, port, username, password)

    players = yield from lms.create_players()

    hass.data[DATA_SQUEEZEBOX].extend(players)
    async_add_devices(players)

    @asyncio.coroutine
    def async_service_handler(service):
        """Map services to methods on MediaPlayerDevice."""
        method = SERVICE_TO_METHOD.get(service.service)
        if not method:
            return

        params = {key: value for key, value in service.data.items()
                  if key != 'entity_id'}
        entity_ids = service.data.get('entity_id')
        if entity_ids:
            target_players = [player for player in hass.data[DATA_SQUEEZEBOX]
                              if player.entity_id in entity_ids]
        else:
            target_players = hass.data[DATA_SQUEEZEBOX]

        update_tasks = []
        for player in target_players:
            yield from getattr(player, method['method'])(**params)
            update_tasks.append(player.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service]['schema']
        hass.services.async_register(
            DOMAIN, service, async_service_handler,
            schema=schema)

    return True


class LogitechMediaServer(object):
    """Representation of a Logitech media server."""

    def __init__(self, hass, host, port, username, password):
        """Initialize the Logitech device."""
        self.hass = hass
        self.host = host
        self.port = port
        self._username = username
        self._password = password

    @asyncio.coroutine
    def create_players(self):
        """Create a list of devices connected to LMS."""
        result = []
        data = yield from self.async_query('players', 'status')
        if data is False:
            return result
        for players in data.get('players_loop', []):
            player = SqueezeBoxDevice(
                self, players['playerid'], players['name'])
            yield from player.async_update()
            result.append(player)
        return result

    @asyncio.coroutine
    def async_query(self, *command, player=""):
        """Abstract out the JSON-RPC connection."""
        auth = None if self._username is None else aiohttp.BasicAuth(
            self._username, self._password)
        url = "http://{}:{}/jsonrpc.js".format(
            self.host, self.port)
        data = json.dumps({
            "id": "1",
            "method": "slim.request",
            "params": [player, command]
            })

        _LOGGER.debug("URL: %s Data: %s", url, data)

        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(TIMEOUT, loop=self.hass.loop):
                response = yield from websession.post(
                    url,
                    data=data,
                    auth=auth)

                if response.status != 200:
                    _LOGGER.error(
                        "Query failed, response code: %s Full message: %s",
                        response.status, response)
                    return False

                data = yield from response.json()

        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Failed communicating with LMS: %s", type(error))
            return False

        try:
            return data['result']
        except AttributeError:
            _LOGGER.error("Received invalid response: %s", data)
            return False


class SqueezeBoxDevice(MediaPlayerDevice):
    """Representation of a SqueezeBox device."""

    def __init__(self, lms, player_id, name):
        """Initialize the SqueezeBox device."""
        super(SqueezeBoxDevice, self).__init__()
        self._lms = lms
        self._id = player_id
        self._status = {}
        self._name = name
        self._last_update = None
        _LOGGER.debug("Creating SqueezeBox object: %s, %s", name, player_id)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._id

    @property
    def state(self):
        """Return the state of the device."""
        if 'power' in self._status and self._status['power'] == 0:
            return STATE_OFF
        if 'mode' in self._status:
            if self._status['mode'] == 'pause':
                return STATE_PAUSED
            if self._status['mode'] == 'play':
                return STATE_PLAYING
            if self._status['mode'] == 'stop':
                return STATE_IDLE
        return STATE_UNKNOWN

    def async_query(self, *parameters):
        """Send a command to the LMS.

        This method must be run in the event loop and returns a coroutine.
        """
        return self._lms.async_query(
            *parameters, player=self._id)

    @asyncio.coroutine
    def async_update(self):
        """Retrieve the current state of the player."""
        tags = 'adKl'
        response = yield from self.async_query(
            "status", "-", "1", "tags:{tags}"
            .format(tags=tags))

        if response is False:
            return

        self._status = {}

        try:
            self._status.update(response["playlist_loop"][0])
        except KeyError:
            pass
        try:
            self._status.update(response["remoteMeta"])
        except KeyError:
            pass

        self._status.update(response)
        self._last_update = utcnow()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if 'mixer volume' in self._status:
            return int(float(self._status['mixer volume'])) / 100.0

    @property
    def is_volume_muted(self):
        """Return true if volume is muted."""
        if 'mixer volume' in self._status:
            return str(self._status['mixer volume']).startswith('-')

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        if 'current_title' in self._status:
            return self._status['current_title']

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if 'duration' in self._status:
            return int(float(self._status['duration']))

    @property
    def media_position(self):
        """Duration of current playing media in seconds."""
        if 'time' in self._status:
            return int(float(self._status['time']))

    @property
    def media_position_updated_at(self):
        """Last time status was updated."""
        return self._last_update

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if 'artwork_url' in self._status:
            media_url = self._status['artwork_url']
        elif 'id' in self._status:
            media_url = ('/music/{track_id}/cover.jpg').format(
                track_id=self._status['id'])
        else:
            media_url = ('/music/current/cover.jpg?player={player}').format(
                player=self._id)

        # pylint: disable=protected-access
        if self._lms._username:
            base_url = 'http://{username}:{password}@{server}:{port}/'.format(
                username=self._lms._username,
                password=self._lms._password,
                server=self._lms.host,
                port=self._lms.port)
        else:
            base_url = 'http://{server}:{port}/'.format(
                server=self._lms.host,
                port=self._lms.port)

        url = urllib.parse.urljoin(base_url, media_url)

        return url

    @property
    def media_title(self):
        """Title of current playing media."""
        if 'title' in self._status:
            return self._status['title']

        if 'current_title' in self._status:
            return self._status['current_title']

    @property
    def media_artist(self):
        """Artist of current playing media."""
        if 'artist' in self._status:
            return self._status['artist']

    @property
    def media_album_name(self):
        """Album of current playing media."""
        if 'album' in self._status:
            return self._status['album']

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        if 'playlist_shuffle' in self._status:
            return self._status['playlist_shuffle'] == 1

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_SQUEEZEBOX

    def async_turn_off(self):
        """Turn off media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('power', '0')

    def async_volume_up(self):
        """Volume up media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('mixer', 'volume', '+5')

    def async_volume_down(self):
        """Volume down media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('mixer', 'volume', '-5')

    def async_set_volume_level(self, volume):
        """Set volume level, range 0..1.

        This method must be run in the event loop and returns a coroutine.
        """
        volume_percent = str(int(volume*100))
        return self.async_query('mixer', 'volume', volume_percent)

    def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player.

        This method must be run in the event loop and returns a coroutine.
        """
        mute_numeric = '1' if mute else '0'
        return self.async_query('mixer', 'muting', mute_numeric)

    def async_media_play_pause(self):
        """Send pause command to media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('pause')

    def async_media_play(self):
        """Send play command to media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('play')

    def async_media_pause(self):
        """Send pause command to media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('pause', '1')

    def async_media_next_track(self):
        """Send next track command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('playlist', 'index', '+1')

    def async_media_previous_track(self):
        """Send next track command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('playlist', 'index', '-1')

    def async_media_seek(self, position):
        """Send seek command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('time', position)

    def async_turn_on(self):
        """Turn the media player on.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_query('power', '1')

    def async_play_media(self, media_type, media_id, **kwargs):
        """
        Send the play_media command to the media player.

        If ATTR_MEDIA_ENQUEUE is True, add `media_id` to the current playlist.
        This method must be run in the event loop and returns a coroutine.
        """
        if kwargs.get(ATTR_MEDIA_ENQUEUE):
            return self._add_uri_to_playlist(media_id)

        return self._play_uri(media_id)

    def _play_uri(self, media_id):
        """Replace the current play list with the uri."""
        return self.async_query('playlist', 'play', media_id)

    def _add_uri_to_playlist(self, media_id):
        """Add a items to the existing playlist."""
        return self.async_query('playlist', 'add', media_id)

    def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        return self.async_query('playlist', 'shuffle', int(shuffle))

    def async_clear_playlist(self):
        """Send the media player the command for clear playlist."""
        return self.async_query('playlist', 'clear')

    def async_call_method(self, command, parameters=None):
        """
        Call Squeezebox JSON/RPC method.

        Escaped optional parameters are added to the command to form the list
        of positional parameters (p0, p1...,  pN) passed to JSON/RPC server.
        """
        all_params = [command]
        if parameters:
            for parameter in parameters:
                all_params.append(urllib.parse.quote(parameter, safe=':=/?'))
        return self.async_query(*all_params)
