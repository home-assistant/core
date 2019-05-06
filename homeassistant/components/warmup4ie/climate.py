"""Platform that offers a connection to a warmup4ie device."""
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_ROOM,
    TEMP_CELSIUS)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_AWAY_MODE, SUPPORT_OPERATION_MODE,
    SUPPORT_ON_OFF, STATE_AUTO, STATE_MANUAL)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_AWAY_MODE |
                 SUPPORT_OPERATION_MODE | SUPPORT_ON_OFF)

CONF_LOCATION = 'location'
CONF_TARGET_TEMP = 'target_temp'

DEFAULT_NAME = 'warmup4ie'
DEFAULT_TARGET_TEMP = 20

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_LOCATION): cv.string,
    vol.Required(CONF_ROOM): cv.string,
    vol.Optional(CONF_TARGET_TEMP,
                 default=DEFAULT_TARGET_TEMP): vol.Coerce(float),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo climate devices."""
    _LOGGER.info("Setting up platform for Warmup4IE component")
    name = config.get(CONF_NAME)
    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    location = config.get(CONF_LOCATION)
    room = config.get(CONF_ROOM)
    target_temp = config.get(CONF_TARGET_TEMP)

    from warmup4ie import Warmup4IEDevice
    device = Warmup4IEDevice(user, password, location, room,
                             target_temp)
    if device is None or not device.setup_finished:
        raise PlatformNotReady

    add_entities(
        [Warmup4IE(hass, name, device)])


class Warmup4IE(ClimateDevice):
    """Representation of a Warmup4IE device."""

    mode_map = {'prog': STATE_AUTO, 'fixed': STATE_MANUAL}

    def __init__(self, hass, name, device):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup4IE component")
        self._name = name
        self._support_flags = SUPPORT_FLAGS
        self._operation_list = [STATE_AUTO, STATE_MANUAL]
        self._unit_of_measurement = TEMP_CELSIUS
        self._away = False
        self._on = True
        self._current_operation_mode = STATE_MANUAL
        self._device = device

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_current_temmperature()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.get_target_temmperature()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._device.get_target_temperature_low()

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._device.get_target_temperature_high()

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._on

    @property
    def operation_list(self):
        """Return the operation modes list."""
        return self._operation_list

    @property
    def current_operation(self):
        """Return current operation ie. manual, auto, frost."""
        return self._current_operation_mode

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._device.set_new_temperature(kwargs.get(ATTR_TEMPERATURE))

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self._device.set_location_to_frost()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self._device.set_temperature_to_manual()

    def set_operation_mode(self, operation_mode):
        """
        Set new target operation mode.

        Switch device on if was previously off
        """
        if not self.is_on:
            self._on = True
        if operation_mode == STATE_AUTO:
            self._device.set_temperature_to_auto()
            self._current_operation_mode = operation_mode
            return
        if operation_mode == STATE_MANUAL:
            self._device.set_temperature_to_manual()
            self._current_operation_mode = operation_mode

    def turn_on(self):
        """Turn on."""
        self._on = True
        self._device.set_temperature_to_manual()

    def turn_off(self):
        """Turn off."""
        self._on = False
        self._device.set_location_to_off()

    def update(self):
        """Fetch new state data for this device.

        This is the only method that should fetch new data for Home Assistant.
        """
        if not self._device.update_room():
            _LOGGER.error("Updating Warmup4IE component failed")

        # set operation mode
        self._current_operation_mode = self.mode_map.get(
            self._device.get_run_mode(), STATE_MANUAL)

        # set whether device is in away mode
        if self._device.get_run_mode() == 'away':
            self._away = True
        else:
            self._away = False

        # set whether device is on/off
        if self._device.get_run_mode() == 'off':
            self._on = False
        else:
            self._on = True
