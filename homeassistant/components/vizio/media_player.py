"""Vizio SmartCast Device support."""
from datetime import timedelta
import logging

from pyvizio import Vizio
import voluptuous as vol

from homeassistant import util
from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
)

from . import VIZIO_SCHEMA, validate_auth
from .const import CONF_VOLUME_STEP, DEFAULT_NAME, DEVICE_ID, ICON

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

COMMON_SUPPORTED_COMMANDS = (
    SUPPORT_SELECT_SOURCE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
)

SUPPORTED_COMMANDS = {
    "soundbar": COMMON_SUPPORTED_COMMANDS,
    "tv": (COMMON_SUPPORTED_COMMANDS | SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK),
}


PLATFORM_SCHEMA = vol.All(PLATFORM_SCHEMA.extend(VIZIO_SCHEMA), validate_auth)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Vizio media player platform."""
    host = config[CONF_HOST]
    token = config.get(CONF_ACCESS_TOKEN)
    name = config[CONF_NAME]
    volume_step = config[CONF_VOLUME_STEP]
    device_type = config[CONF_DEVICE_CLASS]
    device = VizioDevice(host, token, name, volume_step, device_type)
    if not device.validate_setup():
        fail_auth_msg = ""
        if token:
            fail_auth_msg = " and auth token is correct"
        _LOGGER.error(
            "Failed to set up Vizio platform, please check if host "
            "is valid and available%s",
            fail_auth_msg,
        )
        return

    add_entities([device], True)


class VizioDevice(MediaPlayerDevice):
    """Media Player implementation which performs REST requests to device."""

    def __init__(self, host, token, name, volume_step, device_type):
        """Initialize Vizio device."""

        self._name = name
        self._state = None
        self._volume_level = None
        self._volume_step = volume_step
        self._current_input = None
        self._available_inputs = None
        self._device_type = device_type
        self._supported_commands = SUPPORTED_COMMANDS[device_type]
        self._device = Vizio(DEVICE_ID, host, DEFAULT_NAME, token, device_type)
        self._max_volume = float(self._device.get_max_volume())
        self._unique_id = None
        self._icon = ICON[device_type]

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve latest state of the device."""
        is_on = self._device.get_power_state()

        if not self._unique_id:
            self._unique_id = self._device.get_esn()

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
    def icon(self):
        """Return the icon of the device."""
        return self._icon

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

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return self._unique_id

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
        self._device.vol_up(num=self._volume_step)
        if self._volume_level is not None:
            self._volume_level = min(
                1.0, self._volume_level + self._volume_step / self._max_volume
            )

    def volume_down(self):
        """Decreasing volume of the device."""
        self._device.vol_down(num=self._volume_step)
        if self._volume_level is not None:
            self._volume_level = max(
                0.0, self._volume_level - self._volume_step / self._max_volume
            )

    def validate_setup(self):
        """Validate if host is available and auth token is correct."""
        return self._device.can_connect()

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
