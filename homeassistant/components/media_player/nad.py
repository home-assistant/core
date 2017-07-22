"""
Support for interfacing with NAD receivers through RS-232.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.nad/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_MUTE, SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE, MediaPlayerDevice,
    PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['nad_receiver==0.0.6']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'NAD Receiver'
DEFAULT_MIN_VOLUME = -92
DEFAULT_MAX_VOLUME = -20

SUPPORT_NAD = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | \
    SUPPORT_SELECT_SOURCE

CONF_SERIAL_PORT = 'serial_port'
CONF_MIN_VOLUME = 'min_volume'
CONF_MAX_VOLUME = 'max_volume'
CONF_SOURCE_DICT = 'sources'

SOURCE_DICT_SCHEMA = vol.Schema({
    vol.Range(min=1, max=10): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SERIAL_PORT): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MIN_VOLUME, default=DEFAULT_MIN_VOLUME): int,
    vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): int,
    vol.Optional(CONF_SOURCE_DICT, default={}): SOURCE_DICT_SCHEMA,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the NAD platform."""
    from nad_receiver import NADReceiver
    add_devices([NAD(
        config.get(CONF_NAME),
        NADReceiver(config.get(CONF_SERIAL_PORT)),
        config.get(CONF_MIN_VOLUME),
        config.get(CONF_MAX_VOLUME),
        config.get(CONF_SOURCE_DICT)
    )])


class NAD(MediaPlayerDevice):
    """Representation of a NAD Receiver."""

    def __init__(self, name, nad_receiver, min_volume, max_volume,
                 source_dict):
        """Initialize the NAD Receiver device."""
        self._name = name
        self._nad_receiver = nad_receiver
        self._min_volume = min_volume
        self._max_volume = max_volume
        self._source_dict = source_dict
        self._reverse_mapping = {value: key for key, value in
                                 self._source_dict.items()}

        self._volume = None
        self._state = None
        self._mute = None
        self._source = None

        self.update()

    def calc_volume(self, decibel):
        """
        Calculate the volume given the decibel.

        Return the volume (0..1).
        """
        return abs(self._min_volume - decibel) / abs(
            self._min_volume - self._max_volume)

    def calc_db(self, volume):
        """
        Calculate the decibel given the volume.

        Return the dB.
        """
        return self._min_volume + round(
            abs(self._min_volume - self._max_volume) * volume)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Retrieve latest state."""
        if self._nad_receiver.main_power('?') == 'Off':
            self._state = STATE_OFF
        else:
            self._state = STATE_ON

        if self._nad_receiver.main_mute('?') == 'Off':
            self._mute = False
        else:
            self._mute = True

        self._volume = self.calc_volume(self._nad_receiver.main_volume('?'))
        self._source = self._source_dict.get(
            self._nad_receiver.main_source('?'))

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_NAD

    def turn_off(self):
        """Turn the media player off."""
        self._nad_receiver.main_power('=', 'Off')

    def turn_on(self):
        """Turn the media player on."""
        self._nad_receiver.main_power('=', 'On')

    def volume_up(self):
        """Volume up the media player."""
        self._nad_receiver.main_volume('+')

    def volume_down(self):
        """Volume down the media player."""
        self._nad_receiver.main_volume('-')

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._nad_receiver.main_volume('=', self.calc_db(volume))

    def select_source(self, source):
        """Select input source."""
        self._nad_receiver.main_source('=', self._reverse_mapping.get(source))

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return sorted(list(self._reverse_mapping.keys()))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self._nad_receiver.main_mute('=', 'On')
        else:
            self._nad_receiver.main_mute('=', 'Off')
