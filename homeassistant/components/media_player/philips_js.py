"""
Media Player component to integrate TVs exposing the Joint Space API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.philips_js/
"""
import logging
from datetime import timedelta
import json

import requests
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_MUTE, MediaPlayerDevice)
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNKNOWN, CONF_HOST, CONF_NAME)
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

SUPPORT_PHILIPS_JS = SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | \
                     SUPPORT_VOLUME_MUTE | SUPPORT_SELECT_SOURCE

DEFAULT_DEVICE = 'default'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_NAME = 'Philips TV'
DEVICE_BASE_URL = 'http://{0}:1925/1/{1}'
DEVICE_NAME_URL = 'http://{0}:1925/1/system/name'
DEVICE_INPUT_URL = 'http://{0}:1925/1/input/key'
DEVICE_SRC_SET_URL = 'http://{0}:1925/1/sources/current'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Philips TV platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    add_devices([PhilipsJS(host, name)])


# pylint: disable=too-many-instance-attributes,abstract-method
class PhilipsJS(MediaPlayerDevice):
    """Representation of a Philips TV exposing the JointSpace API."""

    def __init__(self, host, name):
        """Initialize the Philips TV."""
        self._host = host
        self._name = name
        self._state = STATE_UNKNOWN
        self._min_volume = None
        self._max_volume = None
        self._volume = None
        self._muted = False
        self._program_name = None
        self._channel_name = None
        self._source = None
        self._source_list = []
        self._connfail = 0
        self._source_mapping = {}

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_PHILIPS_JS

    @property
    def state(self):
        """Get the device state. An exception means OFF state."""
        try:
            if self._connfail:
                self._connfail -= 1
                self._source = None
                return STATE_OFF
            requests.get(DEVICE_NAME_URL.format(self._host), timeout=5)
            self._state = STATE_ON
            return self._state
        except requests.exceptions.RequestException:
            self._connfail = 5
            return STATE_OFF

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    def select_source(self, source):
        """Set the input source."""
        if source in self._source_mapping:
            data = dict(id=self._source_mapping[source])
            try:
                resp = requests.post(DEVICE_SRC_SET_URL.format(self._host),
                                     data=json.dumps(data), timeout=5)
                if resp.status_code == 200:
                    self._source = source
            except requests.exceptions.RequestException:
                _LOGGER.error('Could not set source to %s', source)
        else:
            _LOGGER.warning('invalid source: %s', source)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is not None:
            return self._volume
        else:
            return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    def turn_off(self):
        """Turn off the device."""
        self.send_key('Standby')

    def volume_up(self):
        """Send volume up command."""
        self.send_key('VolumeUp')

    def volume_down(self):
        """Send volume down command."""
        self.send_key('VolumeDown')

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_key('Mute')

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._source

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest date and update device state."""
        try:
            if self._connfail:
                _LOGGER.debug('Conn-Fail:  %i', self._connfail)
                self._connfail -= 1
                return
            audiodata = json.loads(requests.get(
                DEVICE_BASE_URL.format(self._host, 'audio/volume')).text)
            self._min_volume = int(audiodata['min'])
            self._max_volume = int(audiodata['max'])
            self._volume = audiodata['current']
            self._muted = audiodata['muted']
            srcid = json.loads(requests.get(
                DEVICE_BASE_URL.format(self._host,
                                           'sources/current')).text)['id']
            srcdict = json.loads(requests.get(
                DEVICE_BASE_URL.format(self._host, 'sources')).text)
            self._source = srcdict[srcid]['name']
            if not self._source_list:
                for srcid in sorted(srcdict):
                    self._source_list.append(srcdict[srcid]['name'])
                    self._source_mapping[srcdict[srcid]['name']] = srcid
            self._state = STATE_ON
        except requests.exceptions.RequestException:
            self._connfail = 5
            self._state = STATE_OFF
            self._source = None

    def send_key(self, key):
        """Send key command to TV."""
        try:
            if self._connfail:
                self._connfail -= 1
                _LOGGER.debug('Conn-Fail:  %i', self._connfail)
                return False
            data = dict(key=key)
            requests.post(DEVICE_INPUT_URL.format(self._host),
                          data=json.dumps(data), timeout=5)
            return True
        except requests.exceptions.RequestException:
            _LOGGER.error('Could not send key %s', key)
            self._connfail = 5
            self._state = STATE_OFF
            self._source = None
            return False
