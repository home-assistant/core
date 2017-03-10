"""
Support for interfacing with the XBMC/Kodi JSON-RPC API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.kodi/
"""
import asyncio
from functools import wraps
import logging
import urllib

import aiohttp
import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_PLAY_MEDIA, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_PLAY, SUPPORT_VOLUME_STEP, MediaPlayerDevice,
    PLATFORM_SCHEMA)
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING, CONF_HOST, CONF_NAME,
    CONF_PORT, CONF_SSL, CONF_USERNAME, CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['jsonrpc-async==0.4', 'jsonrpc-websocket==0.2']

_LOGGER = logging.getLogger(__name__)

CONF_TCP_PORT = 'tcp_port'
CONF_TURN_OFF_ACTION = 'turn_off_action'
CONF_ENABLE_WEBSOCKET = 'enable_websocket'

DEFAULT_NAME = 'Kodi'
DEFAULT_PORT = 8080
DEFAULT_TCP_PORT = 9090
DEFAULT_TIMEOUT = 5
DEFAULT_SSL = False
DEFAULT_ENABLE_WEBSOCKET = True

TURN_OFF_ACTION = [None, 'quit', 'hibernate', 'suspend', 'reboot', 'shutdown']

SUPPORT_KODI = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_SEEK | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_PLAY | SUPPORT_VOLUME_STEP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): cv.port,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_TURN_OFF_ACTION, default=None): vol.In(TURN_OFF_ACTION),
    vol.Inclusive(CONF_USERNAME, 'auth'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'auth'): cv.string,
    vol.Optional(CONF_ENABLE_WEBSOCKET, default=DEFAULT_ENABLE_WEBSOCKET):
        cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Kodi platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    tcp_port = config.get(CONF_TCP_PORT)
    encryption = config.get(CONF_SSL)
    websocket = config.get(CONF_ENABLE_WEBSOCKET)

    if host.startswith('http://') or host.startswith('https://'):
        host = host.lstrip('http://').lstrip('https://')
        _LOGGER.warning(
            "Kodi host name should no longer conatin http:// See updated "
            "definitions here: "
            "https://home-assistant.io/components/media_player.kodi/")

    entity = KodiDevice(
        hass,
        name=config.get(CONF_NAME),
        host=host, port=port, tcp_port=tcp_port, encryption=encryption,
        username=config.get(CONF_USERNAME),
        password=config.get(CONF_PASSWORD),
        turn_off_action=config.get(CONF_TURN_OFF_ACTION), websocket=websocket)

    async_add_devices([entity], update_before_add=True)


def cmd(func):
    """Decorator to catch command exceptions."""
    @wraps(func)
    @asyncio.coroutine
    def wrapper(obj, *args, **kwargs):
        """Wrapper for all command methods."""
        import jsonrpc_base
        try:
            yield from func(obj, *args, **kwargs)
        except jsonrpc_base.jsonrpc.TransportError as exc:
            # If Kodi is off, we expect calls to fail.
            if obj.state == STATE_OFF:
                log_function = _LOGGER.info
            else:
                log_function = _LOGGER.error
            log_function("Error calling %s on entity %s: %r",
                         func.__name__, obj.entity_id, exc)
    return wrapper


class KodiDevice(MediaPlayerDevice):
    """Representation of a XBMC/Kodi device."""

    def __init__(self, hass, name, host, port, tcp_port, encryption=False,
                 username=None, password=None, turn_off_action=None,
                 websocket=True):
        """Initialize the Kodi device."""
        import jsonrpc_async
        import jsonrpc_websocket
        self.hass = hass
        self._name = name

        kwargs = {
            'timeout': DEFAULT_TIMEOUT,
            'session': async_get_clientsession(hass),
        }

        if username is not None:
            kwargs['auth'] = aiohttp.BasicAuth(username, password)
            image_auth_string = "{}:{}@".format(username, password)
        else:
            image_auth_string = ""

        http_protocol = 'https' if encryption else 'http'
        ws_protocol = 'wss' if encryption else 'ws'

        self._http_url = '{}://{}:{}/jsonrpc'.format(http_protocol, host, port)
        self._image_url = '{}://{}{}:{}/image'.format(
            http_protocol, image_auth_string, host, port)
        self._ws_url = '{}://{}:{}/jsonrpc'.format(ws_protocol, host, tcp_port)

        self._http_server = jsonrpc_async.Server(self._http_url, **kwargs)
        if websocket:
            # Setup websocket connection
            self._ws_server = jsonrpc_websocket.Server(self._ws_url, **kwargs)

            # Register notification listeners
            self._ws_server.Player.OnPause = self.async_on_speed_event
            self._ws_server.Player.OnPlay = self.async_on_speed_event
            self._ws_server.Player.OnSpeedChanged = self.async_on_speed_event
            self._ws_server.Player.OnStop = self.async_on_stop
            self._ws_server.Application.OnVolumeChanged = \
                self.async_on_volume_changed
            self._ws_server.System.OnQuit = self.async_on_quit
            self._ws_server.System.OnRestart = self.async_on_quit
            self._ws_server.System.OnSleep = self.async_on_quit

            def on_hass_stop(event):
                """Close websocket connection when hass stops."""
                self.hass.async_add_job(self._ws_server.close())

            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, on_hass_stop)
        else:
            self._ws_server = None

        self._turn_off_action = turn_off_action
        self._enable_websocket = websocket
        self._players = list()
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self._ws_connected = False

    @callback
    def async_on_speed_event(self, sender, data):
        """Called when player changes between playing and paused."""
        self._properties['speed'] = data['player']['speed']

        if not hasattr(data['item'], 'id'):
            # If no item id is given, perform a full update
            force_refresh = True
        else:
            # If a new item is playing, force a complete refresh
            force_refresh = data['item']['id'] != self._item.get('id')

        self.hass.async_add_job(self.async_update_ha_state(force_refresh))

    @callback
    def async_on_stop(self, sender, data):
        """Called when the player stops playback."""
        # Prevent stop notifications which are sent after quit notification
        if self._players is None:
            return

        self._players = []
        self._properties = {}
        self._item = {}
        self.hass.async_add_job(self.async_update_ha_state())

    @callback
    def async_on_volume_changed(self, sender, data):
        """Called when the volume is changed."""
        self._app_properties['volume'] = data['volume']
        self._app_properties['muted'] = data['muted']
        self.hass.async_add_job(self.async_update_ha_state())

    @callback
    def async_on_quit(self, sender, data):
        """Called when the volume is changed."""
        self._players = None
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self.hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def _get_players(self):
        """Return the active player objects or None."""
        import jsonrpc_base
        try:
            return (yield from self.server.Player.GetActivePlayers())
        except jsonrpc_base.jsonrpc.TransportError:
            if self._players is not None:
                _LOGGER.info('Unable to fetch kodi data')
                _LOGGER.debug('Unable to fetch kodi data', exc_info=True)
            return None

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
    def async_ws_connect(self):
        """Connect to Kodi via websocket protocol."""
        import jsonrpc_base
        try:
            yield from self._ws_server.ws_connect()
        except jsonrpc_base.jsonrpc.TransportError:
            _LOGGER.info("Unable to connect to Kodi via websocket")
            _LOGGER.debug(
                "Unable to connect to Kodi via websocket", exc_info=True)
            # Websocket connection is not required. Just return.
            return
        self.hass.loop.create_task(self.async_ws_loop())
        self._ws_connected = True

    @asyncio.coroutine
    def async_ws_loop(self):
        """Run the websocket asyncio message loop."""
        import jsonrpc_base
        try:
            yield from self._ws_server.ws_loop()
        except jsonrpc_base.jsonrpc.TransportError:
            # Kodi abruptly ends ws connection when exiting. We only need to
            # know that it was closed.
            pass
        finally:
            yield from self._ws_server.close()
            self._ws_connected = False

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        self._players = yield from self._get_players()

        if self._players is None:
            self._properties = {}
            self._item = {}
            self._app_properties = {}
            return

        if self._enable_websocket and not self._ws_connected:
            self.hass.loop.create_task(self.async_ws_connect())

        self._app_properties = \
            yield from self.server.Application.GetProperties(
                ['volume', 'muted']
            )

        if len(self._players) > 0:
            player_id = self._players[0]['playerid']

            assert isinstance(player_id, int)

            self._properties = yield from self.server.Player.GetProperties(
                player_id,
                ['time', 'totaltime', 'speed', 'live']
            )

            self._item = (yield from self.server.Player.GetItem(
                player_id,
                ['title', 'file', 'uniqueid', 'thumbnail', 'artist']
            ))['item']
        else:
            self._properties = {}
            self._item = {}
            self._app_properties = {}

    @property
    def server(self):
        """Active server for json-rpc requests."""
        if self._ws_connected:
            return self._ws_server
        else:
            return self._http_server

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return not self._ws_connected

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if 'volume' in self._app_properties:
            return self._app_properties['volume'] / 100.0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._app_properties.get('muted')

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._item.get('uniqueid', None)

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self._players is not None and len(self._players) > 0:
            return self._players[0]['type']

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._properties.get('live'):
            return None

        total_time = self._properties.get('totaltime')

        if total_time is None:
            return None

        return (
            total_time['hours'] * 3600 +
            total_time['minutes'] * 60 +
            total_time['seconds'])

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        thumbnail = self._item.get('thumbnail')
        if thumbnail is None:
            return None

        url_components = urllib.parse.urlparse(thumbnail)
        if url_components.scheme == 'image':
            return '{}/{}'.format(
                self._image_url,
                urllib.parse.quote_plus(thumbnail))

    @property
    def media_title(self):
        """Title of current playing media."""
        # find a string we can use as a title
        return self._item.get(
            'title', self._item.get('label', self._item.get('file')))

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supported_features = SUPPORT_KODI

        if self._turn_off_action in TURN_OFF_ACTION:
            supported_features |= SUPPORT_TURN_OFF

        return supported_features

    @cmd
    @asyncio.coroutine
    def async_turn_off(self):
        """Execute turn_off_action to turn off media player."""
        if self._turn_off_action == 'quit':
            yield from self.server.Application.Quit()
        elif self._turn_off_action == 'hibernate':
            yield from self.server.System.Hibernate()
        elif self._turn_off_action == 'suspend':
            yield from self.server.System.Suspend()
        elif self._turn_off_action == 'reboot':
            yield from self.server.System.Reboot()
        elif self._turn_off_action == 'shutdown':
            yield from self.server.System.Shutdown()
        else:
            _LOGGER.warning('turn_off requested but turn_off_action is none')

    @cmd
    @asyncio.coroutine
    def async_volume_up(self):
        """Volume up the media player."""
        assert (
            yield from self.server.Input.ExecuteAction('volumeup')) == 'OK'

    @cmd
    @asyncio.coroutine
    def async_volume_down(self):
        """Volume down the media player."""
        assert (
            yield from self.server.Input.ExecuteAction('volumedown')) == 'OK'

    @cmd
    def async_set_volume_level(self, volume):
        """Set volume level, range 0..1.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.server.Application.SetVolume(int(volume * 100))

    @cmd
    def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.server.Application.SetMute(mute)

    @asyncio.coroutine
    def async_set_play_state(self, state):
        """Helper method for play/pause/toggle."""
        players = yield from self._get_players()

        if players is not None and len(players) != 0:
            yield from self.server.Player.PlayPause(
                players[0]['playerid'], state)

    @cmd
    def async_media_play_pause(self):
        """Pause media on media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_set_play_state('toggle')

    @cmd
    def async_media_play(self):
        """Play media.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_set_play_state(True)

    @cmd
    def async_media_pause(self):
        """Pause the media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_set_play_state(False)

    @cmd
    @asyncio.coroutine
    def async_media_stop(self):
        """Stop the media player."""
        players = yield from self._get_players()

        if len(players) != 0:
            yield from self.server.Player.Stop(players[0]['playerid'])

    @asyncio.coroutine
    def _goto(self, direction):
        """Helper method used for previous/next track."""
        players = yield from self._get_players()

        if len(players) != 0:
            if direction == 'previous':
                # first seek to position 0. Kodi goes to the beginning of the
                # current track if the current track is not at the beginning.
                yield from self.server.Player.Seek(players[0]['playerid'], 0)

            yield from self.server.Player.GoTo(
                players[0]['playerid'], direction)

    @cmd
    def async_media_next_track(self):
        """Send next track command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self._goto('next')

    @cmd
    def async_media_previous_track(self):
        """Send next track command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self._goto('previous')

    @cmd
    @asyncio.coroutine
    def async_media_seek(self, position):
        """Send seek command."""
        players = yield from self._get_players()

        time = {}

        time['milliseconds'] = int((position % 1) * 1000)
        position = int(position)

        time['seconds'] = int(position % 60)
        position /= 60

        time['minutes'] = int(position % 60)
        position /= 60

        time['hours'] = int(position)

        if len(players) != 0:
            yield from self.server.Player.Seek(players[0]['playerid'], time)

    @cmd
    def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player.

        This method must be run in the event loop and returns a coroutine.
        """
        if media_type == "CHANNEL":
            return self.server.Player.Open(
                {"item": {"channelid": int(media_id)}})
        else:
            return self.server.Player.Open(
                {"item": {"file": str(media_id)}})
