"""
Support for interfacing with NAD receivers through telnet.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.nadtelnet/
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

REQUIREMENTS = ['nad_receiver==0.0.11']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'NAD Receiver'
DEFAULT_MIN_VOLUME = -92
DEFAULT_MAX_VOLUME = -20

SUPPORT_NAD = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | \
    SUPPORT_SELECT_SOURCE

CONF_NAD_HOST = 'host'
CONF_MIN_VOLUME = 'min_volume'
CONF_MAX_VOLUME = 'max_volume'
CONF_SOURCE_DICT = 'sources'

SOURCE_DICT_SCHEMA = vol.Schema({
    vol.Range(min=1, max=10): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAD_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MIN_VOLUME, default=DEFAULT_MIN_VOLUME): int,
    vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): int,
    vol.Optional(CONF_SOURCE_DICT, default={}): SOURCE_DICT_SCHEMA,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the NAD platform."""
    from nad_receiver import NADReceiverTelnet
    add_devices([NADTelnet(
        config.get(CONF_NAME),
        NADReceiverTelnet(config.get(CONF_NAD_HOST)),
        config.get(CONF_MIN_VOLUME),
        config.get(CONF_MAX_VOLUME),
        config.get(CONF_SOURCE_DICT)
    )], True)


class NADTelnet(MediaPlayerDevice):
    """Representation of a NAD Receiver."""

    def __init__(self, name, nad_receiver, min_volume, max_volume,
                 source_dict):
        """Initialize the NAD Receiver device."""
        self._name = name
        self._receiver = nad_receiver
        self._min_volume = min_volume
        self._max_volume = max_volume
        self._source_dict = source_dict
        self._reverse_mapping = {value: key for key, value in
                                 self._source_dict.items()}

        self._volume = self._state = self._mute = self._source = None

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
        try:
            if self._receiver.main_power('?') == 'Off':
                self._state = STATE_OFF
            else:
                self._state = STATE_ON

            if self._receiver.main_mute('?') == 'Off':
                self._mute = False
            else:
                self._mute = True

            self._volume = self._receiver.main_volume('?')
            self._source = self._source_dict.get(
                self._receiver.main_source('?'))
        except:
            # Could be that the NAD got turned off
            self._state = STATE_OFF
            _LOGGER.debug("Communications with NAD failed")

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
        try:
            self._receiver.main_power('=', 'Off')
        except:
            _LOGGER.debug("Communications with NAD failed")
            pass

    def turn_on(self):
        """Turn the media player on."""
        try:
            self._receiver.main_power('=', 'On')
        except:
            _LOGGER.debug("Communications with NAD failed")
            pass

    def volume_up(self):
        """Volume up the media player."""
        try:
            self._receiver.main_volume('+')
        except:
            _LOGGER.debug("Communications with NAD failed")
            pass

    def volume_down(self):
        """Volume down the media player."""
        try:
            self._receiver.main_volume('-')
        except:
            _LOGGER.debug("Communications with NAD failed")
            pass

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        try:
            self._receiver.main_volume('=', volume)
        except:
            _LOGGER.debug("Communications with NAD failed")
            pass

    def select_source(self, source):
        """Select input source."""
        try:
            self._receiver.main_source('=', self._reverse_mapping.get(source))
        except:
            _LOGGER.debug("Communications with NAD failed")
            pass

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
        try:
            if mute:
                self._receiver.main_mute('=', 'On')
            else:
                self._receiver.main_mute('=', 'Off')
        except:
            _LOGGER.debug("Communications with NAD failed")
            pass
