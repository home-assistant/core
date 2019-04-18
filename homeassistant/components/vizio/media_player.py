"""Vizio SmartCast Device support."""
from datetime import timedelta
import logging
import voluptuous as vol
from homeassistant import util
from homeassistant.components.media_player import (
    MediaPlayerDevice,
    PLATFORM_SCHEMA
)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON
)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_SUPPRESS_WARNING = 'suppress_warning'
CONF_VOLUME_STEP = 'volume_step'

DEFAULT_NAME = 'Vizio SmartCast'
DEFAULT_VOLUME_STEP = 1
DEFAULT_DEVICE_CLASS = 'tv'
DEVICE_ID = 'pyvizio'
DEVICE_NAME = 'Python Vizio'

ICON = 'mdi:television'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

COMMON_SUPPORTED_COMMANDS = (
    SUPPORT_SELECT_SOURCE |
    SUPPORT_TURN_ON |
    SUPPORT_TURN_OFF |
    SUPPORT_VOLUME_MUTE |
    SUPPORT_VOLUME_SET |
    SUPPORT_VOLUME_STEP
)

SUPPORTED_COMMANDS = {
    'soundbar': COMMON_SUPPORTED_COMMANDS,
    'tv': (
        COMMON_SUPPORTED_COMMANDS |
        SUPPORT_NEXT_TRACK |
        SUPPORT_PREVIOUS_TRACK
    )
}


def validate_auth(config):
    """Validate presence of CONF_ACCESS_TOKEN when CONF_DEVICE_CLASS=tv."""
    token = config.get(CONF_ACCESS_TOKEN)
    if config[CONF_DEVICE_CLASS] == 'tv' and (token is None or token == ''):
        raise vol.Invalid(
            "When '{}' is 'tv' then '{}' is required.".format(
                CONF_DEVICE_CLASS,
                CONF_ACCESS_TOKEN,
            ),
            path=[CONF_ACCESS_TOKEN],
        )
    return config


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_ACCESS_TOKEN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SUPPRESS_WARNING, default=False): cv.boolean,
        vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS):
            vol.All(cv.string, vol.Lower, vol.In(['tv', 'soundbar'])),
        vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
    }),
    validate_auth,
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Vizio media player platform."""
    host = config[CONF_HOST]
    token = config.get(CONF_ACCESS_TOKEN)
    name = config[CONF_NAME]
    volume_step = config[CONF_VOLUME_STEP]
    device_type = config[CONF_DEVICE_CLASS]
    device = VizioDevice(host, token, name, volume_step, device_type)
    if device.validate_setup() is False:
        fail_auth_msg = ""
        if token is not None and token != '':
            fail_auth_msg = " and auth token is correct"
        _LOGGER.error("Failed to set up Vizio platform, please check if host "
                      "is valid and available%s", fail_auth_msg)
        return

    if config[CONF_SUPPRESS_WARNING]:
        from requests.packages import urllib3
        _LOGGER.warning("InsecureRequestWarning is disabled "
                        "because of Vizio platform configuration")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    add_entities([device], True)


class VizioDevice(MediaPlayerDevice):
    """Media Player implementation which performs REST requests to device."""

    def __init__(self, host, token, name, volume_step, device_type):
        """Initialize Vizio device."""
        import pyvizio

        self._name = name
        self._state = None
        self._volume_level = None
        self._volume_step = volume_step
        self._current_input = None
        self._available_inputs = None
        self._device_type = device_type
        self._supported_commands = SUPPORTED_COMMANDS[device_type]
        self._device = pyvizio.Vizio(DEVICE_ID, host, DEFAULT_NAME, token,
                                     device_type)
        self._max_volume = float(self._device.get_max_volume())

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve latest state of the device."""
        is_on = self._device.get_power_state()

        if is_on:
            self._state = STATE_ON

            volume = self._device.get_current_volume()
            if volume is not None:
                self._volume_level = float(volume) / self._max_volume

            input_ = self._device.get_current_input()
            if input_ is not None:
                self._current_input = input_.meta_name

            inputs = self._device.get_inputs()
            if inputs is not None:
                self._available_inputs = [input_.name for input_ in inputs]

        else:
            if is_on is None:
                self._state = None
            else:
                self._state = STATE_OFF

            self._volume_level = None
            self._current_input = None
            self._available_inputs = None

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def volume_level(self):
        """Return the volume level of the device."""
        return self._volume_level

    @property
    def source(self):
        """Return current input of the device."""
        return self._current_input

    @property
    def source_list(self):
        """Return list of available inputs of the device."""
        return self._available_inputs

    @property
    def supported_features(self):
        """Flag device features that are supported."""
        return self._supported_commands

    def turn_on(self):
        """Turn the device on."""
        self._device.pow_on()

    def turn_off(self):
        """Turn the device off."""
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
        """Increasing volume of the device."""
        self._volume_level += self._volume_step / self._max_volume
        self._device.vol_up(num=self._volume_step)

    def volume_down(self):
        """Decreasing volume of the device."""
        self._volume_level -= self._volume_step / self._max_volume
        self._device.vol_down(num=self._volume_step)

    def validate_setup(self):
        """Validate if host is available and auth token is correct."""
        return self._device.get_current_volume() is not None

    def set_volume_level(self, volume):
        """Set volume level."""
        if self._volume_level is not None:
            if volume > self._volume_level:
                num = int(self._max_volume * (volume - self._volume_level))
                self._volume_level = volume
                self._device.vol_up(num=num)
            elif volume < self._volume_level:
                num = int(self._max_volume * (self._volume_level - volume))
                self._volume_level = volume
                self._device.vol_down(num=num)
