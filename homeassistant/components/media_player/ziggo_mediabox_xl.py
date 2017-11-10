"""
Support for interface with a Ziggo Mediabox XL.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.ziggo_mediabox_xl/
"""
import logging
import socket
import requests

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, MediaPlayerDevice,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE,
    SUPPORT_PLAY, SUPPORT_PAUSE)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN,
    STATE_PAUSED, STATE_PLAYING)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

KNOWN_DEVICES_KEY = 'ziggo_mediabox_xl_known_devices'

SUPPORT_ZIGGO = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
    SUPPORT_NEXT_TRACK | SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Ziggo Mediabox XL platform."""
    known_devices = hass.data.get(KNOWN_DEVICES_KEY)
    if known_devices is None:
        known_devices = set()
        hass.data[KNOWN_DEVICES_KEY] = known_devices

    # Is this a manual configuration?
    if config.get(CONF_HOST) is not None:
        host = config.get(CONF_HOST)
        name = config.get(CONF_NAME)
    elif discovery_info is not None:
        host = discovery_info.get('host')
        name = discovery_info.get('name')
    else:
        _LOGGER.warning("Cannot determine device")
        return

    # Only add a device once, so discovered devices do not override manual
    # config.
    hosts = []
    ip_addr = socket.gethostbyname(host)
    if ip_addr not in known_devices:
        sock = socket.socket()
        try:
            state = sock.connect_ex((ip_addr, 5900))
        except socket.error:
            _LOGGER.error("Couldn't connect to %s", ip_addr)
        if state == 0:
            hosts.append(ZiggoMediaboxXLDevice(ip_addr, name))
            known_devices.add(ip_addr)
        else:
            _LOGGER.error("Can't connect to %s", host)
    else:
        _LOGGER.warning("Ignoring duplicate Ziggo Mediabox XL %s", host)
    add_devices(hosts, True)


class ZiggoMediaboxXLDevice(MediaPlayerDevice):
    """Representation of a Ziggo Mediabox XL Device."""

    def __init__(self, host, name):
        """Initialize the device."""
        # Generate a configuration for the Samsung library
        self._host = host
        self._port = {"state": 62137, "cmd": 5900}
        self._name = name
        self._state = STATE_UNKNOWN
        self._channels = {}
        self._keys = {
            "POWER": "E0 00", "OK": "E0 01", "BACK": "E0 02",
            "CHAN_UP": "E0 06", "CHAN_DOWN": "E0 07",
            "HELP": "E0 09", "MENU": "E0 0A", "GUIDE": "E0 0B",
            "INFO": "EO 0E", "TEXT": "E0 0F", "MENU1": "E0 11",
            "MENU2": "EO 15", "DPAD_UP": "E1 00",
            "DPAD_DOWN": "E1 01", "DPAD_LEFT": "E1 02",
            "DPAD_RIGHT": "E1 03", "PAUSE": "E4 00", "STOP": "E4 02",
            "RECORD": "E4 04", "FWD": "E4 05", "RWD": "E4 07",
            "MENU3": "E4 07", "ONDEMAND": "EF 28", "DVR": "EF 29",
            "TV": "EF 2A"}
        for i in range(10):
            self._keys["NUM_{}".format(i)] = "E3 {:02d}".format(i)
        self._fetch_channels()

    def update(self):
        """Retrieve the state of the device."""
        # Send an empty key to see if we are still connected
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sock.connect_ex((self._host, self._port['state'])) == 0:
                if self._state != STATE_PAUSED:
                    self._state = STATE_PLAYING
            else:
                self._state = STATE_OFF
            sock.close()
        except socket.error:
            _LOGGER.error("Couldn't fetch state from %s", self._host)

    def send_keys(self, keys):
        """Send keys to the device and handle exceptions."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self._host, self._port['cmd']))
            # mandatory dance
            version_info = sock.recv(15)
            sock.send(version_info)
            sock.recv(2)
            sock.send(bytes.fromhex('01'))
            sock.recv(4)
            sock.recv(24)
            for key in keys:
                if key in self._keys:
                    sock.send(bytes.fromhex("04 01 00 00 00 00 " +
                                            self._keys[key]))
                    sock.send(bytes.fromhex("04 00 00 00 00 00 " +
                                            self._keys[key]))
                else:
                    _LOGGER.error("%s key not supported", key)
            sock.close()
        except socket.error:
            _LOGGER.error("Couldn't connect to %s", self._host)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def source_list(self):
        """List of available sources (channels)."""
        return [self._channels[c]
                for c in sorted(self._channels.keys())]

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ZIGGO

    def turn_on(self):
        """Turn the media player on."""
        self.send_keys(['POWER'])
        self._state = STATE_OFF

    def turn_off(self):
        """Turn off media player."""
        self.send_keys(['POWER'])
        self._state = STATE_ON

    def media_play(self):
        """Send play command."""
        self.send_keys(['PLAY'])
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self.send_keys(['PAUSE'])
        self._state = STATE_PAUSED

    def media_play_pause(self):
        """Simulate play pause media player."""
        self.send_keys(['PAUSE'])
        if self._state == STATE_PAUSED:
            self._state = STATE_PLAYING
        else:
            self._state = STATE_PAUSED

    def media_next_track(self):
        """Channel up."""
        self.send_keys(['CHAN_UP'])
        self._state = STATE_PLAYING

    def media_previous_track(self):
        """Channel down."""
        self.send_keys(['CHAN_DOWN'])
        self._state = STATE_PLAYING

    def select_source(self, source):
        """Select the channel."""
        if str(source).isdigit():
            digits = str(source)
        elif source in self._channels.values():
            for key, value in self._channels.items():
                if value == source:
                    digits = key
                    break
        else:
            return

        self.send_keys(['NUM_{}'.format(digit)
                        for digit in str(digits)])
        self._state = STATE_PLAYING

    def _fetch_channels(self):
        json = requests.get(
            'https://restapi.ziggo.nl/1.0/channels-overview').json()
        self._channels = {c['channel']['code']: c['channel']['name']
                          for c in json['channels']}
