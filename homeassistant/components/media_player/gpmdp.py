"""
Support for Google Play Music Desktop Player.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.gpmdp/
"""
import logging
import json
import os
import socket

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_PAUSE, MediaPlayerDevice)
from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_OFF)
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['websocket-client==0.37.0']
SUPPORT_GPMDP = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK
GPMDP_CONFIG_FILE = 'gpmpd.conf'
_CONFIGURING = {}


def request_configuration(hass, config, websocket, add_devices_callback):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')
    if 'gpmdp' in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING['gpmdp'], "Failed to register, please try again.")

        return

    # pylint: disable=unused-argument
    def gpmdp_configuration_callback(callback_data):
        """The actions to do when our configuration callback is called."""
        while True:
            msg = json.loads(websocket.recv())
            if msg['channel'] == 'connect':
                if msg['payload'] == "CODE_REQUIRED":
                    websocket.send('{"namespace": "connect",'
                                   '"method": "connect",'
                                   '"arguments": ["Home Assistant",'
                                   ' "' + callback_data.get('pin') + '"]}')
                    tmpmsg = json.loads(websocket.recv())
                    if tmpmsg['channel'] == 'time':
                        _LOGGER.error('Error setting up GPMDP. Please pause'
                                      'the desktop player and try again.')
                        break
                    code = tmpmsg['payload']
                    if code == 'CODE_REQUIRED':
                        continue
                    setup_gpmdp(hass, config, code,
                                add_devices_callback)
                    config_from_file(hass.config.path(GPMDP_CONFIG_FILE),
                                     {"CODE": code})
                    websocket.send('{"namespace": "connect",'
                                   '"method": "connect",'
                                   '"arguments": ["Home Assistant",'
                                   ' "' + code + '"]}')
                    websocket.close()
                    break

    _CONFIGURING['gpmdp'] = configurator.request_config(
        hass, "GPM Desktop Player", gpmdp_configuration_callback,
        description=(
            'Enter the pin that is displayed in the '
            'Google Play Music Desktop Player.'),
        submit_caption="Submit",
        fields=[{'id': 'pin', 'name': 'Pin Code', 'type': 'number'}]
    )


def setup_gpmdp(hass, config, code, add_devices_callback):
    """Setup gpmdp."""
    from websocket import create_connection
    name = config.get("name", "GPM Desktop Player")
    address = config.get("address")
    if not code:
        websocket = create_connection(("ws://" + address + ":5672"), timeout=1)
        websocket.send('{"namespace": "connect", "method": "connect",'
                       '"arguments": ["Home Assistant"]}')
        request_configuration(hass, config, websocket, add_devices_callback)
        return

    if 'gpmdp' in _CONFIGURING:
        configurator = get_component('configurator')
        configurator.request_done(_CONFIGURING.pop('gpmdp'))

    if address is None:
        _LOGGER.error("Missing address in config")
        return False

    add_devices_callback([GPMDP(name, address, code, create_connection)])


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We're writing configuration
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error('Saving config file failed: %s', error)
            return False
        return True
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error('Reading config file failed: %s', error)
                # This won't work yet
                return False
        else:
            return {}


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the GPMDP platform."""
    codeconfig = config_from_file(hass.config.path(GPMDP_CONFIG_FILE))
    if len(codeconfig):
        code = codeconfig.get("CODE")
    elif discovery_info is not None:
        if 'gpmdp' in _CONFIGURING:
            return
        code = None
    else:
        code = None
    setup_gpmdp(hass, config, code, add_devices_callback)


class GPMDP(MediaPlayerDevice):
    """Representation of a GPMDP."""

    # pylint: disable=too-many-public-methods, abstract-method
    # pylint: disable=too-many-instance-attributes
    def __init__(self, name, address, code, create_connection):
        """Initialize the media player."""
        self._connection = create_connection
        self._address = address
        self._authorization_code = code
        self._name = name
        self._status = STATE_OFF
        self._ws = None
        self._title = None
        self._artist = None
        self._albumart = None
        self.update()

    def get_ws(self):
        """Check if the websocket is setup and connected."""
        if self._ws is None:
            try:
                self._ws = self._connection(("ws://" + self._address +
                                             ":5672"), timeout=1)
                self._ws.send('{"namespace": "connect", "method": "connect",'
                              '"arguments": ["Home Assistant",'
                              ' "' + self._authorization_code + '"]}')
            except (socket.timeout, ConnectionRefusedError,
                    ConnectionResetError):
                self._ws = None
        return self._ws

    def update(self):
        """Get the latest details from the player."""
        websocket = self.get_ws()
        if websocket is None:
            self._status = STATE_OFF
            return
        else:
            receiving = True
            while receiving:
                from websocket import _exceptions
                try:
                    msg = json.loads(websocket.recv())
                    if msg['channel'] == 'lyrics':
                        receiving = False  # end of now playing data
                    elif msg['channel'] == 'playState':
                        if msg['payload'] is True:
                            self._status = STATE_PLAYING
                        else:
                            self._status = STATE_PAUSED
                    elif msg['channel'] == 'track':
                        self._title = (msg['payload']['title'])
                        self._artist = (msg['payload']['artist'])
                        self._albumart = (msg['payload']['albumArt'])
                except (_exceptions.WebSocketTimeoutException,
                        _exceptions.WebSocketProtocolException,
                        _exceptions.WebSocketPayloadException):
                    return

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
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_GPMDP

    def media_next_track(self):
        """Send media_next command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send('{"namespace": "playback", "method": "forward"}')

    def media_previous_track(self):
        """Send media_previous command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send('{"namespace": "playback", "method": "rewind"}')

    def media_play(self):
        """Send media_play command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send('{"namespace": "playback", "method": "playPause"}')
        self._status = STATE_PLAYING
        self.update_ha_state()

    def media_pause(self):
        """Send media_pause command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send('{"namespace": "playback", "method": "playPause"}')
        self._status = STATE_PAUSED
        self.update_ha_state()
