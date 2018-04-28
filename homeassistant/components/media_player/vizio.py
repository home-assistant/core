"""
Vizio SmartCast TV support.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.vizio/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, MediaPlayerDevice)
from homeassistant.const import (
    CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON,
    STATE_UNKNOWN)
from homeassistant.helpers import config_validation as cv
import homeassistant.util as util

REQUIREMENTS = ['pyvizio==0.0.3']

_LOGGER = logging.getLogger(__name__)

CONF_SUPPRESS_WARNING = 'suppress_warning'
CONF_VOLUME_STEP = 'volume_step'

DEFAULT_NAME = 'Vizio SmartCast'
DEFAULT_VOLUME_STEP = 1
DEVICE_ID = 'pyvizio'
DEVICE_NAME = 'Python Vizio'

ICON = 'mdi:television'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SUPPORTED_COMMANDS = SUPPORT_TURN_ON | SUPPORT_TURN_OFF \
                     | SUPPORT_SELECT_SOURCE \
                     | SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK \
                     | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SUPPRESS_WARNING, default=False): cv.boolean,
    vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the VizioTV media player platform."""
    host = config.get(CONF_HOST)
    token = config.get(CONF_ACCESS_TOKEN)
    name = config.get(CONF_NAME)
    volume_step = config.get(CONF_VOLUME_STEP)

    device = VizioDevice(host, token, name, volume_step)
    if device.validate_setup() is False:
        _LOGGER.error("Failed to setup Vizio TV platform, "
                      "please check if host and API key are correct")
        return

    if config.get(CONF_SUPPRESS_WARNING):
        from requests.packages import urllib3
        _LOGGER.warning("InsecureRequestWarning is disabled "
                        "because of Vizio platform configuration")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    add_devices([device], True)


class VizioDevice(MediaPlayerDevice):
    """Media Player implementation which performs REST requests to TV."""

    def __init__(self, host, token, name, volume_step):
        """Initialize Vizio device."""
        import pyvizio
        self._device = pyvizio.Vizio(DEVICE_ID, host, DEFAULT_NAME, token)
        self._name = name
        self._state = STATE_UNKNOWN
        self._volume_level = None
        self._volume_step = volume_step
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
        self._device.vol_up(num=self._volume_step)

    def volume_down(self):
        """Decreasing volume of the TV."""
        self._device.vol_down(num=self._volume_step)

    def validate_setup(self):
        """Validate if host is available and key is correct."""
        return self._device.get_current_volume() is not None
