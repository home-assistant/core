"""
Support for interfacing with the XBMC/Kodi JSON-RPC API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.kodi/
"""
import asyncio
import json
import logging
import urllib
import uuid

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_PLAY_MEDIA, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_STOP,
    SUPPORT_TURN_OFF, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING, CONF_HOST, CONF_NAME,
    CONF_PORT, CONF_USERNAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['websockets==3.2']

_LOGGER = logging.getLogger(__name__)

CONF_TCP_PORT = 'tcp_port'
CONF_TURN_OFF_ACTION = 'turn_off_action'

DEFAULT_NAME = 'Kodi'
DEFAULT_PORT = 8080
DEFAULT_TCP_PORT = 9090
DEFAULT_TIMEOUT = 5

TURN_OFF_ACTION = [None, 'quit', 'hibernate', 'suspend', 'reboot', 'shutdown']

APPLICATION_NOTIFICATIONS = (
    'Application.OnVolumeChanged',
)

PLAYER_NOTIFICATIONS = (
    'Player.OnPause',
    'Player.OnPlay',
    'Player.OnPropertyChanged',
    'Player.OnSeek',
    'Player.OnSpeedChanged',
    'Player.OnStop',
)

EXIT_NOTIFICATIONS = (
    'System.OnQuit',
    'System.OnRestart',
    'System.OnSleep',
)

JSON_HEADERS = {'content-type': 'application/json'}
JSONRPC_VERSION = '2.0'

ATTR_JSONRPC = 'jsonrpc'
ATTR_METHOD = 'method'
ATTR_PARAMS = 'params'
ATTR_ID = 'id'

SUPPORT_KODI = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_SEEK | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): cv.port,
    vol.Optional(CONF_TURN_OFF_ACTION, default=None): vol.In(TURN_OFF_ACTION),
    vol.Inclusive(CONF_USERNAME, 'auth'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'auth'): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Setup the Kodi platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    tcp_port = config.get(CONF_TCP_PORT)

    if host.startswith('http://') or host.startswith('https://'):
        host = host.lstrip('http://').lstrip('https://')
        _LOGGER.warning(
            "Kodi host name should no longer conatin http:// See updated "
            "definitions here: "
            "https://home-assistant.io/components/media_player.kodi/")

    entity = KodiEntity(
        hass,
        name=config.get(CONF_NAME),
        host=host, port=port, tcp_port=tcp_port,
        username=config.get(CONF_USERNAME),
        password=config.get(CONF_PASSWORD),
        turn_off_action=config.get(CONF_TURN_OFF_ACTION))

    yield from async_add_entities([entity], update_before_add=True)


class KodiEntity(MediaPlayerDevice):
    """Representation of a XBMC/Kodi device."""

    def __init__(self, hass, name, host, port, tcp_port, username=None,
                 password=None, turn_off_action=None):
        """Initialize the Kodi device."""
        self.hass = hass
        self._name = name
        self._turn_off_action = turn_off_action

        if username:
            self._auth = aiohttp.BasicAuth(username, password)
            image_auth_string = "{}:{}@".format(username, password)
        else:
            self._auth = None
            image_auth_string = ""

        self._http_url = 'http://{}:{}/jsonrpc'.format(host, port)
        self._image_url = 'http://{}{}:{}/image'.format(
            image_auth_string, host, port)
        self._ws_url = 'ws://{}:{}/jsonrpc'.format(host, tcp_port)

        self._session = aiohttp.ClientSession(
            auth=self._auth, headers=JSON_HEADERS, loop=hass.loop)
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._close_session)
        self._websocket = None

        self._players = list()
        self._properties = None
        self._item = None
        self._app_properties = None

    @asyncio.coroutine
    def _close_session(self, event):
        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self.hass.loop):
                if self._websocket:
                    yield from self._websocket.close()
                yield from self._session.close()
        except (aiohttp.errors.ClientError,
                asyncio.TimeoutError,
                ConnectionRefusedError):
            pass

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @asyncio.coroutine
    def async_json_request(self, method, *args):
        """Request json information from Kodi.

        Returns None if connection failed.
        """
        data = {
            ATTR_JSONRPC: JSONRPC_VERSION,
            ATTR_METHOD: method,
            ATTR_ID: str(uuid.uuid4()),
        }
        if len(args) > 0:
            data[ATTR_PARAMS] = args

        response = None
        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self.hass.loop):
                response = yield from self._session.post(
                    self._http_url, data=json.dumps(data))

            if response.status == 401:
                _LOGGER.error(
                    "Error fetching Kodi data. HTTP %d Unauthorized. "
                    "Password is incorrect.", response.status)
                return None
            if response.status != 200:
                _LOGGER.error(
                    "Error fetching Kodi data. HTTP %d", response.status)
                return None

            response_json = yield from response.json()
            if 'error' in response_json:
                _LOGGER.error(
                    "RPC Error Code %d: %s",
                    response_json['error']['code'],
                    response_json['error']['message'])
                return None
            return response_json['result']
        except (aiohttp.errors.ClientError,
                asyncio.TimeoutError,
                ConnectionRefusedError):
            return None
        finally:
            if response:
                response.close()

    @asyncio.coroutine
    def async_websocket_loop(self):
        """Check websocket for push events from Kodi."""
        import websockets

        while True:
            try:
                msg = yield from self._websocket.recv()
            except websockets.exceptions.ConnectionClosed:
                break

            data = json.loads(msg)
            if data[ATTR_METHOD] in EXIT_NOTIFICATIONS:
                self._players = None
                self.hass.async_add_job(self.async_update_ha_state())
                continue

            if data[ATTR_METHOD] in APPLICATION_NOTIFICATIONS:
                if self._app_properties is None:
                    continue
                try:
                    self._app_properties['volume'] = \
                        data[ATTR_PARAMS]['data']['volume']
                except KeyError:
                    pass
                try:
                    self._app_properties['muted'] = \
                        data[ATTR_PARAMS]['data']['muted']
                except KeyError:
                    pass

            if data[ATTR_METHOD] not in PLAYER_NOTIFICATIONS:
                continue

            if self._players is None or len(self._players) == 0:
                try:
                    if (data[ATTR_PARAMS]['data']['player']['playerid']
                            is not None):
                        # Media just started playing. Full update required
                        self.hass.async_add_job(
                            self.async_update_ha_state(True))
                except KeyError:
                    pass
                continue

            if data[ATTR_METHOD] == "Player.OnStop":
                self._players = []
                self._properties = None
                self._item = None
                self.hass.async_add_job(self.async_update_ha_state())
                continue

            try:
                self._properties['speed'] = \
                    data[ATTR_PARAMS]['data']['player']['speed']
            except KeyError:
                pass

            try:
                self._properties['time'] = \
                    data[ATTR_PARAMS]['data']['player']['time']
            except KeyError:
                pass

            try:
                if data[ATTR_PARAMS]['data']['item']['id'] != self._item['id']:
                    # New item is playing. Perform full update.
                    self.hass.async_add_job(self.async_update_ha_state(True))
                    continue
            except KeyError:
                pass

            # Update HA with changed state
            self.hass.async_add_job(self.async_update_ha_state())

        # Exiting websocket loop
        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self.hass.loop):
                yield from self._websocket.close()
        except (aiohttp.errors.ClientError,
                asyncio.TimeoutError,
                ConnectionRefusedError):
            pass
        self._websocket = None

    @property
    def state(self):
        """Return the state of the device."""
        if self._players is None:
            return STATE_OFF

        if len(self._players) == 0:
            return STATE_IDLE

        if self._properties['speed'] == 0 and not self._properties['live']:
            return STATE_PAUSED
        else:
            return STATE_PLAYING

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        import websockets

        self._app_properties = (yield from self.async_json_request(
            "Application.GetProperties",
            ['volume', 'muted']
        ))

        self._players = yield from self.async_json_request(
            "Player.GetActivePlayers")

        if self._players is None:
            return

        if len(self._players) == 0:
            self._properties = None
            self._item = None
        else:
            player_id = self._players[0]['playerid']

            assert isinstance(player_id, int)

            self._properties = (yield from self.async_json_request(
                "Player.GetProperties", player_id,
                ['time', 'totaltime', 'speed', 'live']
            ))

            self._item = (yield from self.async_json_request(
                "Player.GetItem", player_id,
                ['title', 'file', 'uniqueid', 'thumbnail', 'artist']
            ))['item']

        if self._websocket:
            return

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self.hass.loop):
                self._websocket = yield from websockets.connect(
                    self._ws_url)
            self.hass.loop.create_task(self.async_websocket_loop())
        except (asyncio.TimeoutError,
                ConnectionRefusedError) as error:
            self._websocket = None
            _LOGGER.warning("Error connecting to websocket. %s", error)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._app_properties is not None:
            return self._app_properties['volume'] / 100.0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        if self._app_properties is not None:
            return self._app_properties['muted']

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        if self._item is not None:
            return self._item.get('uniqueid', None)

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self._players is not None and len(self._players) > 0:
            return self._players[0]['type']

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._properties is not None and not self._properties['live']:
            total_time = self._properties['totaltime']

            return (
                total_time['hours'] * 3600 +
                total_time['minutes'] * 60 +
                total_time['seconds'])

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._item is not None:
            return self._get_image_url()

    def _get_image_url(self):
        """Helper function that parses the thumbnail URLs used by Kodi."""
        url_components = urllib.parse.urlparse(self._item['thumbnail'])

        if url_components.scheme == 'image':
            return '{}/{}'.format(
                self._image_url,
                urllib.parse.quote_plus(self._item['thumbnail']))

    @property
    def media_title(self):
        """Title of current playing media."""
        # find a string we can use as a title
        if self._item is not None:
            return self._item.get(
                'title',
                self._item.get('label', self._item.get('file', 'unknown')))

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        supported_media_commands = SUPPORT_KODI

        if self._turn_off_action in TURN_OFF_ACTION:
            supported_media_commands |= SUPPORT_TURN_OFF

        return supported_media_commands

    @asyncio.coroutine
    def async_turn_off(self):
        """Execute turn_off_action to turn off media player."""
        if self._turn_off_action == 'quit':
            yield from self.async_json_request('Application.Quit')
        elif self._turn_off_action == 'hibernate':
            yield from self.async_json_request('System.Hibernate')
        elif self._turn_off_action == 'suspend':
            yield from self.async_json_request('System.Suspend')
        elif self._turn_off_action == 'reboot':
            yield from self.async_json_request('System.Reboot')
        elif self._turn_off_action == 'shutdown':
            yield from self.async_json_request('System.Shutdown')
        else:
            _LOGGER.warning('turn_off requested but turn_off_action is none')

    @asyncio.coroutine
    def async_volume_up(self):
        """Volume up the media player."""
        yield from self.async_json_request(
            'Input.ExecuteAction', 'volumeup')

    @asyncio.coroutine
    def async_volume_down(self):
        """Volume down the media player."""
        yield from self.async_json_request(
            'Input.ExecuteAction', 'volumedown')

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        yield from self.async_json_request(
            'Application.SetVolume', int(volume * 100))

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        yield from self.async_json_request(
            'Application.SetMute', mute)

    @asyncio.coroutine
    def _set_play_state(self, state):
        """Helper method for play/pause/toggle."""
        players = yield from self.async_json_request(
            "Player.GetActivePlayers")

        if len(players) != 0:
            yield from self.async_json_request(
                'Player.PlayPause', players[0]['playerid'], state)

    def async_media_play_pause(self):
        """Pause media on media player."""
        return self._set_play_state('toggle')

    def async_media_play(self):
        """Play media."""
        return self._set_play_state(True)

    def async_media_pause(self):
        """Pause the media player."""
        return self._set_play_state(False)

    @asyncio.coroutine
    def async_media_stop(self):
        """Stop the media player."""
        players = yield from self.async_json_request(
            "Player.GetActivePlayers")

        if len(players) != 0:
            yield from self.async_json_request(
                'Player.Stop', players[0]['playerid'])

    @asyncio.coroutine
    def _goto(self, direction):
        """Helper method used for previous/next track."""
        players = yield from self.async_json_request(
            "Player.GetActivePlayers")

        if len(players) != 0:
            if direction == 'previous':
                # first seek to position 0. Kodi goes to the beginning of the
                # current track if the current track is not at the beginning.
                yield from self.async_json_request(
                    'Player.Seek', players[0]['playerid'], 0)

            yield from self.async_json_request(
                'Player.GoTo', players[0]['playerid'], direction)

    def async_media_next_track(self):
        """Send next track command."""
        return self._goto('next')

    def async_media_previous_track(self):
        """Send next track command."""
        return self._goto('previous')

    @asyncio.coroutine
    def async_media_seek(self, position):
        """Send seek command."""
        players = yield from self.async_json_request(
            "Player.GetActivePlayers")

        time = {}

        time['milliseconds'] = int((position % 1) * 1000)
        position = int(position)

        time['seconds'] = int(position % 60)
        position /= 60

        time['minutes'] = int(position % 60)
        position /= 60

        time['hours'] = int(position)

        if len(players) != 0:
            yield from self.async_json_request(
                'Player.Seek', players[0]['playerid'], time)

    @asyncio.coroutine
    def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        if media_type == "CHANNEL":
            yield from self.async_json_request(
                'Player.Open', {"item": {"channelid": int(media_id)}})
        else:
            yield from self.async_json_request(
                'Player.Open', {"item": {"file": str(media_id)}})
