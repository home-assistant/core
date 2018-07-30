"""
Support for interfacing with the XBMC/Kodi JSON-RPC API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.kodi/
"""
import asyncio
from collections import OrderedDict
from functools import wraps
import logging
import socket
import urllib
import re

import aiohttp
import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_PLAY_MEDIA, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_PLAY, SUPPORT_VOLUME_STEP, SUPPORT_SHUFFLE_SET,
    MediaPlayerDevice, PLATFORM_SCHEMA, MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW,
    MEDIA_TYPE_MOVIE, MEDIA_TYPE_VIDEO, MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_PLAYLIST, MEDIA_PLAYER_SCHEMA, DOMAIN, SUPPORT_TURN_ON)
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING, CONF_HOST, CONF_NAME,
    CONF_PORT, CONF_PROXY_SSL, CONF_USERNAME, CONF_PASSWORD,
    CONF_TIMEOUT, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import script, config_validation as cv
from homeassistant.helpers.template import Template
from homeassistant.util.yaml import dump

REQUIREMENTS = ['jsonrpc-async==0.6', 'jsonrpc-websocket==0.6']

_LOGGER = logging.getLogger(__name__)

EVENT_KODI_CALL_METHOD_RESULT = 'kodi_call_method_result'

CONF_TCP_PORT = 'tcp_port'
CONF_TURN_ON_ACTION = 'turn_on_action'
CONF_TURN_OFF_ACTION = 'turn_off_action'
CONF_ENABLE_WEBSOCKET = 'enable_websocket'

DEFAULT_NAME = 'Kodi'
DEFAULT_PORT = 8080
DEFAULT_TCP_PORT = 9090
DEFAULT_TIMEOUT = 5
DEFAULT_PROXY_SSL = False
DEFAULT_ENABLE_WEBSOCKET = True

DEPRECATED_TURN_OFF_ACTIONS = {
    None: None,
    'quit': 'Application.Quit',
    'hibernate': 'System.Hibernate',
    'suspend': 'System.Suspend',
    'reboot': 'System.Reboot',
    'shutdown': 'System.Shutdown'
}

# https://github.com/xbmc/xbmc/blob/master/xbmc/media/MediaType.h
MEDIA_TYPES = {
    'music': MEDIA_TYPE_MUSIC,
    'artist': MEDIA_TYPE_MUSIC,
    'album': MEDIA_TYPE_MUSIC,
    'song': MEDIA_TYPE_MUSIC,
    'video': MEDIA_TYPE_VIDEO,
    'set': MEDIA_TYPE_PLAYLIST,
    'musicvideo': MEDIA_TYPE_VIDEO,
    'movie': MEDIA_TYPE_MOVIE,
    'tvshow': MEDIA_TYPE_TVSHOW,
    'season': MEDIA_TYPE_TVSHOW,
    'episode': MEDIA_TYPE_TVSHOW,
    # Type 'channel' is used for radio or tv streams from pvr
    'channel': MEDIA_TYPE_CHANNEL,
    # Type 'audio' is used for audio media, that Kodi couldn't scroblle
    'audio': MEDIA_TYPE_MUSIC,
}

SUPPORT_KODI = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
               SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_SEEK | \
               SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_SHUFFLE_SET | \
               SUPPORT_PLAY | SUPPORT_VOLUME_STEP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): cv.port,
    vol.Optional(CONF_PROXY_SSL, default=DEFAULT_PROXY_SSL): cv.boolean,
    vol.Optional(CONF_TURN_ON_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_TURN_OFF_ACTION):
        vol.Any(cv.SCRIPT_SCHEMA, vol.In(DEPRECATED_TURN_OFF_ACTIONS)),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Inclusive(CONF_USERNAME, 'auth'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'auth'): cv.string,
    vol.Optional(CONF_ENABLE_WEBSOCKET, default=DEFAULT_ENABLE_WEBSOCKET):
        cv.boolean,
})

SERVICE_ADD_MEDIA = 'kodi_add_to_playlist'
SERVICE_CALL_METHOD = 'kodi_call_method'

DATA_KODI = 'kodi'

ATTR_MEDIA_TYPE = 'media_type'
ATTR_MEDIA_NAME = 'media_name'
ATTR_MEDIA_ARTIST_NAME = 'artist_name'
ATTR_MEDIA_ID = 'media_id'
ATTR_METHOD = 'method'

MEDIA_PLAYER_ADD_MEDIA_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_TYPE): cv.string,
    vol.Optional(ATTR_MEDIA_ID): cv.string,
    vol.Optional(ATTR_MEDIA_NAME): cv.string,
    vol.Optional(ATTR_MEDIA_ARTIST_NAME): cv.string,
})
MEDIA_PLAYER_CALL_METHOD_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_METHOD): cv.string,
}, extra=vol.ALLOW_EXTRA)

SERVICE_TO_METHOD = {
    SERVICE_ADD_MEDIA: {
        'method': 'async_add_media_to_playlist',
        'schema': MEDIA_PLAYER_ADD_MEDIA_SCHEMA},
    SERVICE_CALL_METHOD: {
        'method': 'async_call_method',
        'schema': MEDIA_PLAYER_CALL_METHOD_SCHEMA},
}


def _check_deprecated_turn_off(hass, turn_off_action):
    """Create an equivalent script for old turn off actions."""
    if isinstance(turn_off_action, str):
        method = DEPRECATED_TURN_OFF_ACTIONS[turn_off_action]
        new_config = OrderedDict(
            [('service', '{}.{}'.format(DOMAIN, SERVICE_CALL_METHOD)),
             ('data_template', OrderedDict(
                 [('entity_id', '{{ entity_id }}'),
                  ('method', method)]))])
        example_conf = dump(OrderedDict(
            [(CONF_TURN_OFF_ACTION, new_config)]))
        _LOGGER.warning(
            "The '%s' action for turn off Kodi is deprecated and "
            "will cease to function in a future release. You need to "
            "change it for a generic Home Assistant script sequence, "
            "which is, for this turn_off action, like this:\n%s",
            turn_off_action, example_conf)
        new_config['data_template'] = OrderedDict(
            [(key, Template(value, hass))
             for key, value in new_config['data_template'].items()])
        turn_off_action = [new_config]
    return turn_off_action


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Kodi platform."""
    if DATA_KODI not in hass.data:
        hass.data[DATA_KODI] = dict()

    # Is this a manual configuration?
    if discovery_info is None:
        name = config.get(CONF_NAME)
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        tcp_port = config.get(CONF_TCP_PORT)
        encryption = config.get(CONF_PROXY_SSL)
        websocket = config.get(CONF_ENABLE_WEBSOCKET)
    else:
        name = "{} ({})".format(DEFAULT_NAME, discovery_info.get('hostname'))
        host = discovery_info.get('host')
        port = discovery_info.get('port')
        tcp_port = DEFAULT_TCP_PORT
        encryption = DEFAULT_PROXY_SSL
        websocket = DEFAULT_ENABLE_WEBSOCKET

    # Only add a device once, so discovered devices do not override manual
    # config.
    ip_addr = socket.gethostbyname(host)
    if ip_addr in hass.data[DATA_KODI]:
        return

    entity = KodiDevice(
        hass,
        name=name,
        host=host, port=port, tcp_port=tcp_port, encryption=encryption,
        username=config.get(CONF_USERNAME),
        password=config.get(CONF_PASSWORD),
        turn_on_action=config.get(CONF_TURN_ON_ACTION),
        turn_off_action=config.get(CONF_TURN_OFF_ACTION),
        timeout=config.get(CONF_TIMEOUT), websocket=websocket)

    hass.data[DATA_KODI][ip_addr] = entity
    async_add_devices([entity], update_before_add=True)

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
            target_players = [player
                              for player in hass.data[DATA_KODI].values()
                              if player.entity_id in entity_ids]
        else:
            target_players = hass.data[DATA_KODI].values()

        update_tasks = []
        for player in target_players:
            yield from getattr(player, method['method'])(**params)

        for player in target_players:
            if player.should_poll:
                update_coro = player.async_update_ha_state(True)
                update_tasks.append(update_coro)

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    if hass.services.has_service(DOMAIN, SERVICE_ADD_MEDIA):
        return

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service]['schema']
        hass.services.async_register(
            DOMAIN, service, async_service_handler,
            schema=schema)


def cmd(func):
    """Catch command exceptions."""
    @wraps(func)
    @asyncio.coroutine
    def wrapper(obj, *args, **kwargs):
        """Wrap all command methods."""
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
                 username=None, password=None,
                 turn_on_action=None, turn_off_action=None,
                 timeout=DEFAULT_TIMEOUT, websocket=True):
        """Initialize the Kodi device."""
        import jsonrpc_async
        import jsonrpc_websocket
        self.hass = hass
        self._name = name

        kwargs = {
            'timeout': timeout,
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
            self._ws_server.Player.OnResume = self.async_on_speed_event
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

        # Script creation for the turn on/off config options
        if turn_on_action is not None:
            turn_on_action = script.Script(
                self.hass, turn_on_action,
                "{} turn ON script".format(self.name),
                self.async_update_ha_state(True))
        if turn_off_action is not None:
            turn_off_action = script.Script(
                self.hass, _check_deprecated_turn_off(hass, turn_off_action),
                "{} turn OFF script".format(self.name))
        self._turn_on_action = turn_on_action
        self._turn_off_action = turn_off_action
        self._enable_websocket = websocket
        self._players = list()
        self._properties = {}
        self._item = {}
        self._app_properties = {}

    @callback
    def async_on_speed_event(self, sender, data):
        """Handle player changes between playing and paused."""
        self._properties['speed'] = data['player']['speed']

        if not hasattr(data['item'], 'id'):
            # If no item id is given, perform a full update
            force_refresh = True
        else:
            # If a new item is playing, force a complete refresh
            force_refresh = data['item']['id'] != self._item.get('id')

        self.async_schedule_update_ha_state(force_refresh)

    @callback
    def async_on_stop(self, sender, data):
        """Handle the stop of the player playback."""
        # Prevent stop notifications which are sent after quit notification
        if self._players is None:
            return

        self._players = []
        self._properties = {}
        self._item = {}
        self.async_schedule_update_ha_state()

    @callback
    def async_on_volume_changed(self, sender, data):
        """Handle the volume changes."""
        self._app_properties['volume'] = data['volume']
        self._app_properties['muted'] = data['muted']
        self.async_schedule_update_ha_state()

    @callback
    def async_on_quit(self, sender, data):
        """Reset the player state on quit action."""
        self._players = None
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self.hass.async_add_job(self._ws_server.close())

    @asyncio.coroutine
    def _get_players(self):
        """Return the active player objects or None."""
        import jsonrpc_base
        try:
            return (yield from self.server.Player.GetActivePlayers())
        except jsonrpc_base.jsonrpc.TransportError:
            if self._players is not None:
                _LOGGER.info("Unable to fetch kodi data")
                _LOGGER.debug("Unable to fetch kodi data", exc_info=True)
            return None

    @property
    def state(self):
        """Return the state of the device."""
        if self._players is None:
            return STATE_OFF

        if not self._players:
            return STATE_IDLE

        if self._properties['speed'] == 0:
            return STATE_PAUSED

        return STATE_PLAYING

    @asyncio.coroutine
    def async_ws_connect(self):
        """Connect to Kodi via websocket protocol."""
        import jsonrpc_base
        try:
            ws_loop_future = yield from self._ws_server.ws_connect()
        except jsonrpc_base.jsonrpc.TransportError:
            _LOGGER.info("Unable to connect to Kodi via websocket")
            _LOGGER.debug(
                "Unable to connect to Kodi via websocket", exc_info=True)
            return

        @asyncio.coroutine
        def ws_loop_wrapper():
            """Catch exceptions from the websocket loop task."""
            try:
                yield from ws_loop_future
            except jsonrpc_base.TransportError:
                # Kodi abruptly ends ws connection when exiting. We will try
                # to reconnect on the next poll.
                pass
            # Update HA state after Kodi disconnects
            self.async_schedule_update_ha_state()

        # Create a task instead of adding a tracking job, since this task will
        # run until the websocket connection is closed.
        self.hass.loop.create_task(ws_loop_wrapper())

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        self._players = yield from self._get_players()

        if self._players is None:
            self._properties = {}
            self._item = {}
            self._app_properties = {}
            return

        if self._enable_websocket and not self._ws_server.connected:
            self.hass.async_add_job(self.async_ws_connect())

        self._app_properties = \
            yield from self.server.Application.GetProperties(
                ['volume', 'muted']
            )

        if self._players:
            player_id = self._players[0]['playerid']

            assert isinstance(player_id, int)

            self._properties = yield from self.server.Player.GetProperties(
                player_id,
                ['time', 'totaltime', 'speed', 'live']
            )

            self._item = (yield from self.server.Player.GetItem(
                player_id,
                ['title', 'file', 'uniqueid', 'thumbnail', 'artist',
                 'albumartist', 'showtitle', 'album', 'season', 'episode']
            ))['item']
        else:
            self._properties = {}
            self._item = {}
            self._app_properties = {}

    @property
    def server(self):
        """Active server for json-rpc requests."""
        if self._enable_websocket and self._ws_server.connected:
            return self._ws_server

        return self._http_server

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return not (self._enable_websocket and self._ws_server.connected)

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
        """Content type of current playing media.

        If the media type cannot be detected, the player type is used.
        """
        if MEDIA_TYPES.get(self._item.get('type')) is None and self._players:
            return MEDIA_TYPES.get(self._players[0]['type'])
        return MEDIA_TYPES.get(self._item.get('type'))

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
        item = self._item
        return item.get('title') or item.get('label') or item.get('file')

    @property
    def media_series_title(self):
        """Title of series of current playing media, TV show only."""
        return self._item.get('showtitle')

    @property
    def media_season(self):
        """Season of current playing media, TV show only."""
        return self._item.get('season')

    @property
    def media_episode(self):
        """Episode of current playing media, TV show only."""
        return self._item.get('episode')

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._item.get('album')

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        artists = self._item.get('artist', [])
        if artists:
            return artists[0]

        return None

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        artists = self._item.get('albumartist', [])
        if artists:
            return artists[0]

        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supported_features = SUPPORT_KODI

        if self._turn_on_action is not None:
            supported_features |= SUPPORT_TURN_ON

        if self._turn_off_action is not None:
            supported_features |= SUPPORT_TURN_OFF

        return supported_features

    @cmd
    @asyncio.coroutine
    def async_turn_on(self):
        """Execute turn_on_action to turn on media player."""
        if self._turn_on_action is not None:
            yield from self._turn_on_action.async_run(
                variables={"entity_id": self.entity_id})
        else:
            _LOGGER.warning("turn_on requested but turn_on_action is none")

    @cmd
    @asyncio.coroutine
    def async_turn_off(self):
        """Execute turn_off_action to turn off media player."""
        if self._turn_off_action is not None:
            yield from self._turn_off_action.async_run(
                variables={"entity_id": self.entity_id})
        else:
            _LOGGER.warning("turn_off requested but turn_off_action is none")

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
        """Handle play/pause/toggle."""
        players = yield from self._get_players()

        if players is not None and players:
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

        if players:
            yield from self.server.Player.Stop(players[0]['playerid'])

    @asyncio.coroutine
    def _goto(self, direction):
        """Handle for previous/next track."""
        players = yield from self._get_players()

        if players:
            if direction == 'previous':
                # First seek to position 0. Kodi goes to the beginning of the
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

        if players:
            yield from self.server.Player.Seek(players[0]['playerid'], time)

    @cmd
    def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player.

        This method must be run in the event loop and returns a coroutine.
        """
        if media_type == "CHANNEL":
            return self.server.Player.Open(
                {"item": {"channelid": int(media_id)}})
        if media_type == "PLAYLIST":
            return self.server.Player.Open(
                {"item": {"playlistid": int(media_id)}})

        return self.server.Player.Open(
            {"item": {"file": str(media_id)}})

    @asyncio.coroutine
    def async_set_shuffle(self, shuffle):
        """Set shuffle mode, for the first player."""
        if not self._players:
            raise RuntimeError("Error: No active player.")
        yield from self.server.Player.SetShuffle(
            {"playerid": self._players[0]['playerid'], "shuffle": shuffle})

    @asyncio.coroutine
    def async_call_method(self, method, **kwargs):
        """Run Kodi JSONRPC API method with params."""
        import jsonrpc_base
        _LOGGER.debug("Run API method %s, kwargs=%s", method, kwargs)
        result_ok = False
        try:
            result = yield from getattr(self.server, method)(**kwargs)
            result_ok = True
        except jsonrpc_base.jsonrpc.ProtocolError as exc:
            result = exc.args[2]['error']
            _LOGGER.error("Run API method %s.%s(%s) error: %s",
                          self.entity_id, method, kwargs, result)
        except jsonrpc_base.jsonrpc.TransportError:
            result = None
            _LOGGER.warning("TransportError trying to run API method "
                            "%s.%s(%s)", self.entity_id, method, kwargs)

        if isinstance(result, dict):
            event_data = {'entity_id': self.entity_id,
                          'result': result,
                          'result_ok': result_ok,
                          'input': {'method': method, 'params': kwargs}}
            _LOGGER.debug("EVENT kodi_call_method_result: %s", event_data)
            self.hass.bus.async_fire(EVENT_KODI_CALL_METHOD_RESULT,
                                     event_data=event_data)
        return result

    @asyncio.coroutine
    def async_add_media_to_playlist(
            self, media_type, media_id=None, media_name='ALL', artist_name=''):
        """Add a media to default playlist (i.e. playlistid=0).

        First the media type must be selected, then
        the media can be specified in terms of id or
        name and optionally artist name.
        All the albums of an artist can be added with
        media_name="ALL"
        """
        import jsonrpc_base
        params = {"playlistid": 0}
        if media_type == "SONG":
            if media_id is None:
                media_id = yield from self.async_find_song(
                    media_name, artist_name)
            if media_id:
                params["item"] = {"songid": int(media_id)}

        elif media_type == "ALBUM":
            if media_id is None:
                if media_name == "ALL":
                    yield from self.async_add_all_albums(artist_name)
                    return

                media_id = yield from self.async_find_album(
                    media_name, artist_name)
            if media_id:
                params["item"] = {"albumid": int(media_id)}

        else:
            raise RuntimeError("Unrecognized media type.")

        if media_id is not None:
            try:
                yield from self.server.Playlist.Add(params)
            except jsonrpc_base.jsonrpc.ProtocolError as exc:
                result = exc.args[2]['error']
                _LOGGER.error("Run API method %s.Playlist.Add(%s) error: %s",
                              self.entity_id, media_type, result)
            except jsonrpc_base.jsonrpc.TransportError:
                _LOGGER.warning("TransportError trying to add playlist to %s",
                                self.entity_id)
        else:
            _LOGGER.warning("No media detected for Playlist.Add")

    @asyncio.coroutine
    def async_add_all_albums(self, artist_name):
        """Add all albums of an artist to default playlist (i.e. playlistid=0).

        The artist is specified in terms of name.
        """
        artist_id = yield from self.async_find_artist(artist_name)

        albums = yield from self.async_get_albums(artist_id)

        for alb in albums['albums']:
            yield from self.server.Playlist.Add(
                {"playlistid": 0, "item": {"albumid": int(alb['albumid'])}})

    @asyncio.coroutine
    def async_clear_playlist(self):
        """Clear default playlist (i.e. playlistid=0)."""
        return self.server.Playlist.Clear({"playlistid": 0})

    @asyncio.coroutine
    def async_get_artists(self):
        """Get artists list."""
        return (yield from self.server.AudioLibrary.GetArtists())

    @asyncio.coroutine
    def async_get_albums(self, artist_id=None):
        """Get albums list."""
        if artist_id is None:
            return (yield from self.server.AudioLibrary.GetAlbums())

        return (yield from self.server.AudioLibrary.GetAlbums(
            {"filter": {"artistid": int(artist_id)}}))

    @asyncio.coroutine
    def async_find_artist(self, artist_name):
        """Find artist by name."""
        artists = yield from self.async_get_artists()
        try:
            out = self._find(
                artist_name, [a['artist'] for a in artists['artists']])
            return artists['artists'][out[0][0]]['artistid']
        except KeyError:
            _LOGGER.warning("No artists were found: %s", artist_name)
            return None

    @asyncio.coroutine
    def async_get_songs(self, artist_id=None):
        """Get songs list."""
        if artist_id is None:
            return (yield from self.server.AudioLibrary.GetSongs())

        return (yield from self.server.AudioLibrary.GetSongs(
            {"filter": {"artistid": int(artist_id)}}))

    @asyncio.coroutine
    def async_find_song(self, song_name, artist_name=''):
        """Find song by name and optionally artist name."""
        artist_id = None
        if artist_name != '':
            artist_id = yield from self.async_find_artist(artist_name)

        songs = yield from self.async_get_songs(artist_id)
        if songs['limits']['total'] == 0:
            return None

        out = self._find(song_name, [a['label'] for a in songs['songs']])
        return songs['songs'][out[0][0]]['songid']

    @asyncio.coroutine
    def async_find_album(self, album_name, artist_name=''):
        """Find album by name and optionally artist name."""
        artist_id = None
        if artist_name != '':
            artist_id = yield from self.async_find_artist(artist_name)

        albums = yield from self.async_get_albums(artist_id)
        try:
            out = self._find(
                album_name, [a['label'] for a in albums['albums']])
            return albums['albums'][out[0][0]]['albumid']
        except KeyError:
            _LOGGER.warning("No albums were found with artist: %s, album: %s",
                            artist_name, album_name)
            return None

    @staticmethod
    def _find(key_word, words):
        key_word = key_word.split(' ')
        patt = [re.compile(
            '(^| )' + k + '( |$)', re.IGNORECASE) for k in key_word]

        out = [[i, 0] for i in range(len(words))]
        for i in range(len(words)):
            mtc = [p.search(words[i]) for p in patt]
            rate = [m is not None for m in mtc].count(True)
            out[i][1] = rate

        return sorted(out, key=lambda out: out[1], reverse=True)
