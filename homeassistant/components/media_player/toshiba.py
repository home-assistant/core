"""
Support for interface with a TOSHIBA CAST TV.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.toshiba/
"""
import logging
import requests

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN, CONF_PORT)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:television'
DEFAULT_NAME = 'Toshiba Cast TV'
DEFAULT_PORT = 4430

SUPPORT_TOSHIBATV = SUPPORT_VOLUME_STEP | \
                    SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
                    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Toshiba Cast TV platform."""
    name = config.get(CONF_NAME)
    port = config.get(CONF_PORT)

    if discovery_info:
        _LOGGER.debug('%s', discovery_info)
        host = discovery_info.get('host')
        port = discovery_info.get('port')
        add_devices([ToshibaCastTVDevice(name, host, port)])
        return True

    host = config.get(CONF_HOST)

    try:
        add_devices([ToshibaCastTVDevice(name, host, port)])
        return True
    except OSError:
        return False


class ToshibaCastTVDevice(MediaPlayerDevice):
    """Representation of a Toshiba cast TV."""

    def __init__(self, name, host, port):
        """Initialize the Toshiba device."""
        self._name = name
        self._muted = False
        self._playing = True
        self._state = STATE_UNKNOWN
        self._host = host
        self._port = port
        self._volume = 0
        self._uniqueid = None
        self._current_source = None
        self._source_list = ['ANT_CABLE', 'CAST', 'HDMI_1',
                             'HDMI_2', 'HDMI_3', 'USB', 'AV']
        self.update()



    def update(self):
        """Retrieve the latest data."""
        try:
            data = requests.get('https://{}:{:d}/v2/remote/uniqueid'.format
                                (self._host, self._port),
                                verify=False).json()
            self._uniqueid = data['uniqueid']

            data = requests.get('https://{}:{:d}/v2/remote/status/power'.format
                                (self._host, self._port),
                                verify=False).json()
            if data['power'] == 'on':
                self._state = STATE_ON
            else:
                self._state = STATE_OFF

            data = requests.get('https://{}:{:d}/v2/remote/status/external_input'.format
                                (self._host, self._port), verify=False).json()
            self._current_source = data['external_input']

            data = requests.get('https://{}:{:d}/v2/remote/status/volume'.format
                                (self._host, self._port),
                                verify=False).json()
            self._volume = data['volume']

        except OSError:
            self._state = STATE_OFF

    def send_key(self, key):
        """Send a key to the tv and handles exceptions."""
        try:
            payload = {'key': key}

            requests.post('https://%s:%s/v2/remote/remote'.format
                          (self._host, self._port),
                          data=payload, verify=False)
            self._state = STATE_ON
        except OSError:
            self._state = STATE_OFF
            return False
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def host(self):
        """Return the host of the device."""
        return self._host

    @property
    def port(self):
        """Return the port of the device."""
        return self._port

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_TOSHIBATV

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._current_source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def volume_level(self):
        """Device volume."""
        return self._volume

    def turn_on(self):
        """Turn on the media player."""
        payload = {'power': 'on'}
        requests.post('https://{}:{:d}/v2/remote/status/power'.format
                      (self._host, self._port),
                      data=payload, verify=False)
        self._state = STATE_ON

    def turn_off(self):
        """Turn off media player."""
        payload = {'power': 'off'}
        requests.post('https://{}:{:d}/v2/remote/status/power'.format
                      (self._host, self._port),
                      data=payload, verify=False)
        self._state = STATE_OFF

    def volume_up(self):
        """Volume up the media player."""
        if self._volume < 100:
            self.send_key('40BF1A')
            self._volume += 1
        self._muted = False

    def volume_down(self):
        """Volume down media player."""
        if self._volume > 0:
            self.send_key('40BF1E')
            self._volume -= 1
        self._muted = False

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_key('40BF10')
        self._muted = not self._muted

    def set_volume_level(self, volume):
        """Set the volume level."""
        self._volume = volume
        payload = {'volume': volume}
        requests.post('https://{}:{:d}/v2/remote/status/volume'.format
                      (self._host, self._port),
                      data=payload, verify=False)

    def select_source(self, source):
        """Select input source."""
        if source in self._source_list:
            payload = {'external_input': source}
            try:
                requests.post('https://{}:{:d}/v2/remote/status/external_input'.format
                             (self._host, self._port),
                              data=payload, verify=False)
                self._current_source = source
            except OSError:
                self._state = STATE_OFF
