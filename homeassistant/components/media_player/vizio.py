"""
Vizio SmartCast TV support.

Usually only 2016+ models come with SmartCast capabilities.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.vizio/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.util as util
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    SUPPORT_TURN_ON,
    SUPPORT_TURN_OFF,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_NEXT_TRACK,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
    MediaPlayerDevice
)
from homeassistant.const import (
    STATE_UNKNOWN,
    STATE_OFF,
    STATE_ON,
    CONF_NAME,
    CONF_HOST,
    CONF_ACCESS_TOKEN
)
from homeassistant.helpers import config_validation as cv

REQUIREMENTS = ['git+https://github.com/vkorn/pyvizio.git'
                '@master#pyvizio==0.0.1']

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:television'
DEFAULT_NAME = 'Vizio SmartCast'
DEVICE_NAME = 'Python Vizio'
DEVICE_ID = 'pyvizio'
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
SUPPORTED_COMMANDS = SUPPORT_TURN_ON | SUPPORT_TURN_OFF \
                     | SUPPORT_SELECT_SOURCE \
                     | SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK \
                     | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the VizioTV media player platform."""
    host = config.get(CONF_HOST)
    if host is None:
        _LOGGER.error('No host info')
        return False
    token = config.get(CONF_ACCESS_TOKEN)
    if token is None:
        _LOGGER.error('No token info')
        return False
    name = config.get(CONF_NAME)

    add_devices([VizioDevice(host, token, name)], True)


class VizioDevice(MediaPlayerDevice):
    """Media Player implementation which performs REST requests to TV."""

    def __init__(self, host, token, name):
        """Initialize Vizio device."""
        import pyvizio
        self._device = pyvizio.Vizio(DEVICE_ID, host, DEFAULT_NAME, token)
        self._name = name
        self._state = STATE_UNKNOWN
        self._volume_level = None
        self._current_input = None
        self._available_inputs = None

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve latest state of the TV."""
        is_on = self._device.get_power_state()
        if is_on is None:
            self._state = STATE_UNKNOWN
            return
        elif is_on is False:
            self._state = STATE_OFF
        else:
            self._state = STATE_ON

        self._volume_level = self._device.get_current_volume()
        input_ = self._device.get_current_input()
        if input_ is not None:
            self._current_input = input_.meta_name
        inputs = self._device.get_inputs()
        if inputs is not None:
            self._available_inputs = []
            for input_ in inputs:
                self._available_inputs.append(input_.name)

    @property
    def state(self):
        """Return the state of the TV."""
        return self._state

    @property
    def name(self):
        """Return the name of the TV."""
        return self._name

    @property
    def volume_level(self):
        """Return the volume level of the TV."""
        return self._volume_level

    @property
    def source(self):
        """Return current input of the TV."""
        return self._current_input

    @property
    def source_list(self):
        """Return list of available inputs of the TV."""
        return self._available_inputs

    @property
    def supported_features(self):
        """Flag TV features that are supported."""
        return SUPPORTED_COMMANDS

    def turn_on(self):
        """Turn the TV player on."""
        self._device.pow_on()

    def turn_off(self):
        """Turn the TV player off."""
        self._device.pow_off()

    def mute_volume(self, mute):
        """Mute the volume."""
        if mute:
            self._device.mute_on()
        else:
            self._device.mute_off()

    def media_previous_track(self):
        """Send previous channel command."""
        self._device.ch_down()

    def media_next_track(self):
        """Send next channel command."""
        self._device.ch_up()

    def select_source(self, source):
        """Select input source."""
        self._device.input_switch(source)

    def volume_up(self):
        """Increasing volume of the TV."""
        self._device.vol_up()

    def volume_down(self):
        """Decreasing volume of the TV."""
        self._device.vol_down()
