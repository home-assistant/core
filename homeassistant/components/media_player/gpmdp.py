"""
Support for Google Play Music Desktop Player.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.gpmdp/
"""
import logging
import json
import socket
import time

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_PAUSE, SUPPORT_VOLUME_SET, SUPPORT_SEEK, SUPPORT_PLAY,
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_OFF, CONF_HOST, CONF_PORT, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['websocket-client==0.37.0']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'GPM Desktop Player'
DEFAULT_PORT = 5672

GPMDP_CONFIG_FILE = 'gpmpd.conf'

SUPPORT_GPMDP = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_SEEK | SUPPORT_VOLUME_SET | SUPPORT_PLAY

PLAYBACK_DICT = {'0': STATE_PAUSED,  # Stopped
                 '1': STATE_PAUSED,
                 '2': STATE_PLAYING}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def request_configuration(hass, config, url, add_devices_callback):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    if 'gpmdp' in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING['gpmdp'], "Failed to register, please try again.")

        return
    from websocket import create_connection
    websocket = create_connection((url), timeout=1)
    websocket.send(json.dumps({'namespace': 'connect',
                               'method': 'connect',
                               'arguments': ['Home Assistant']}))

    def gpmdp_configuration_callback(callback_data):
        """Handle configuration changes."""
        while True:
            from websocket import _exceptions
            try:
                msg = json.loads(websocket.recv())
            except _exceptions.WebSocketConnectionClosedException:
                continue
            if msg['channel'] != 'connect':
                continue
            if msg['payload'] != "CODE_REQUIRED":
                continue
            pin = callback_data.get('pin')
            websocket.send(json.dumps({'namespace': 'connect',
                                       'method': 'connect',
                                       'arguments': ['Home Assistant', pin]}))
            tmpmsg = json.loads(websocket.recv())
            if tmpmsg['channel'] == 'time':
                _LOGGER.error("Error setting up GPMDP. Please pause "
                              "the desktop player and try again")
                break
            code = tmpmsg['payload']
            if code == 'CODE_REQUIRED':
                continue
            setup_gpmdp(hass, config, code,
                        add_devices_callback)
            save_json(hass.config.path(GPMDP_CONFIG_FILE), {"CODE": code})
            websocket.send(json.dumps({'namespace': 'connect',
                                       'method': 'connect',
                                       'arguments': ['Home Assistant', code]}))
            websocket.close()
            break

    _CONFIGURING['gpmdp'] = configurator.request_config(
        DEFAULT_NAME, gpmdp_configuration_callback,
        description=(
            'Enter the pin that is displayed in the '
            'Google Play Music Desktop Player.'),
        submit_caption="Submit",
        fields=[{'id': 'pin', 'name': 'Pin Code', 'type': 'number'}]
    )


def setup_gpmdp(hass, config, code, add_devices):
    """Set up gpmdp."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    url = 'ws://{}:{}'.format(host, port)

    if not code:
        request_configuration(hass, config, url, add_devices)
        return

    if 'gpmdp' in _CONFIGURING:
        configurator = hass.components.configurator
        configurator.request_done(_CONFIGURING.pop('gpmdp'))

    add_devices([GPMDP(name, url, code)], True)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the GPMDP platform."""
    codeconfig = load_json(hass.config.path(GPMDP_CONFIG_FILE))
    if codeconfig:
        code = codeconfig.get('CODE')
    elif discovery_info is not None:
        if 'gpmdp' in _CONFIGURING:
            return
        code = None
    else:
        code = None
    setup_gpmdp(hass, config, code, add_devices)


class GPMDP(MediaPlayerDevice):
    """Representation of a GPMDP."""

    def __init__(self, name, url, code):
        """Initialize the media player."""
        from websocket import create_connection
        self._connection = create_connection
        self._url = url
        self._authorization_code = code
        self._name = name
        self._status = STATE_OFF
        self._ws = None
        self._title = None
        self._artist = None
        self._albumart = None
        self._seek_position = None
        self._duration = None
        self._volume = None
        self._request_id = 0

    def get_ws(self):
        """Check if the websocket is setup and connected."""
        if self._ws is None:
            try:
                self._ws = self._connection((self._url), timeout=1)
                msg = json.dumps({'namespace': 'connect',
                                  'method': 'connect',
                                  'arguments': ['Home Assistant',
                                                self._authorization_code]})
                self._ws.send(msg)
            except (socket.timeout, ConnectionRefusedError,
                    ConnectionResetError):
                self._ws = None
        return self._ws

    def send_gpmdp_msg(self, namespace, method, with_id=True):
        """Send ws messages to GPMDP and verify request id in response."""
        from websocket import _exceptions
        try:
            websocket = self.get_ws()
            if websocket is None:
                self._status = STATE_OFF
                return
            self._request_id += 1
            websocket.send(json.dumps({'namespace': namespace,
                                       'method': method,
                                       'requestID': self._request_id}))
            if not with_id:
                return
            while True:
                msg = json.loads(websocket.recv())
                if 'requestID' in msg:
                    if msg['requestID'] == self._request_id:
                        return msg
        except (ConnectionRefusedError, ConnectionResetError,
                _exceptions.WebSocketTimeoutException,
                _exceptions.WebSocketProtocolException,
                _exceptions.WebSocketPayloadException,
                _exceptions.WebSocketConnectionClosedException):
            self._ws = None

    def update(self):
        """Get the latest details from the player."""
        time.sleep(1)
        playstate = self.send_gpmdp_msg('playback', 'getPlaybackState')
        if playstate is None:
            return
        self._status = PLAYBACK_DICT[str(playstate['value'])]
        time_data = self.send_gpmdp_msg('playback', 'getCurrentTime')
        if time_data is not None:
            self._seek_position = int(time_data['value'] / 1000)
        track_data = self.send_gpmdp_msg('playback', 'getCurrentTrack')
        if track_data is not None:
            self._title = track_data['value']['title']
            self._artist = track_data['value']['artist']
            self._albumart = track_data['value']['albumArt']
            self._duration = int(track_data['value']['duration'] / 1000)
        volume_data = self.send_gpmdp_msg('volume', 'getVolume')
        if volume_data is not None:
            self._volume = volume_data['value'] / 100

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def state(self):
        """Return the state of the device."""
        return self._status

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._title

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self._artist

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._albumart

    @property
    def media_seek_position(self):
        """Time in seconds of current seek position."""
        return self._seek_position

    @property
    def media_duration(self):
        """Time in seconds of current song duration."""
        return self._duration

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_GPMDP

    def media_next_track(self):
        """Send media_next command to media player."""
        self.send_gpmdp_msg('playback', 'forward', False)

    def media_previous_track(self):
        """Send media_previous command to media player."""
        self.send_gpmdp_msg('playback', 'rewind', False)

    def media_play(self):
        """Send media_play command to media player."""
        self.send_gpmdp_msg('playback', 'playPause', False)
        self._status = STATE_PLAYING
        self.schedule_update_ha_state()

    def media_pause(self):
        """Send media_pause command to media player."""
        self.send_gpmdp_msg('playback', 'playPause', False)
        self._status = STATE_PAUSED
        self.schedule_update_ha_state()

    def media_seek(self, position):
        """Send media_seek command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send(json.dumps({'namespace': 'playback',
                                   'method': 'setCurrentTime',
                                   'arguments': [position*1000]}))
        self.schedule_update_ha_state()

    def volume_up(self):
        """Send volume_up command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send('{"namespace": "volume", "method": "increaseVolume"}')
        self.schedule_update_ha_state()

    def volume_down(self):
        """Send volume_down command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send('{"namespace": "volume", "method": "decreaseVolume"}')
        self.schedule_update_ha_state()

    def set_volume_level(self, volume):
        """Set volume on media player, range(0..1)."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send(json.dumps({'namespace': 'volume',
                                   'method': 'setVolume',
                                   'arguments': [volume*100]}))
        self.schedule_update_ha_state()
