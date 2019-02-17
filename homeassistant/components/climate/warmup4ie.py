"""
platform that offers a connection to a warmup4ie device.

this platform is inspired by the following code:
https://github.com/alyc100/SmartThingsPublic/tree/master/devicetypes/alyc100/\
warmup-4ie.src

to setup this component, you need to register to warmup first.
see
https://my.warmup.com/login

Then add to your
configuration.yaml

climate:
  - platform: warmup4ie
    name: YOUR_DESCRIPTION
    username: YOUR_E_MAIL_ADDRESS
    password: YOUR_PASSWORD
    location: YOUR_LOCATION_NAME
    room: YOUR_ROOM_NAME

# the following issues are not yet implemented, since i have currently no need
# for them
# OPEN  - holiday mode still missing
#       - commands for setting/retrieving programmed times missing
"""

import logging
import voluptuous as vol
from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
try:
    from homeassistant.components.climate import (SUPPORT_TARGET_TEMPERATURE,
                                                  SUPPORT_AWAY_MODE,
                                                  SUPPORT_OPERATION_MODE,
                                                  SUPPORT_ON_OFF, STATE_AUTO,
                                                  STATE_MANUAL)
except ImportError:
    from homeassistant.components.climate.const import (
        SUPPORT_TARGET_TEMPERATURE, SUPPORT_AWAY_MODE, SUPPORT_OPERATION_MODE,
        SUPPORT_ON_OFF, STATE_AUTO, STATE_MANUAL)

from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_NAME, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['warmup4ie==0.1.1']

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_AWAY_MODE |
                 SUPPORT_OPERATION_MODE | SUPPORT_ON_OFF)

CONF_LOCATION = 'location'
CONF_ROOM = 'room'
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


# pylint: disable=unused-argument
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo climate devices."""
    name = config.get(CONF_NAME)
    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    location = config.get(CONF_LOCATION)
    room = config.get(CONF_ROOM)
    target_temp = config.get(CONF_TARGET_TEMP)

    add_entities(
        [Warmup4IE(hass, name, user, password, location, room, target_temp)])

# pylint: disable=abstract-method
# pylint: disable=too-many-instance-attributes
# pylint: disable=import-self
# pylint: disable=no-member
class Warmup4IE(ClimateDevice):
    """Representation of a Warmup4IE device."""
    #pylint: disable-msg=too-many-arguments
    def __init__(self, hass, name, user, password, location,
                 room, target_temp):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup4IE component")
        self._name = name
        self._support_flags = SUPPORT_FLAGS
        self._operation_list = [STATE_AUTO, STATE_MANUAL]
        self._unit_of_measurement = TEMP_CELSIUS
        self._away = False
        self._on = True
        self._current_operation_mode = STATE_MANUAL

        import warmup4ie
        self._device = warmup4ie.Warmup4IEDevice(
            user, password, location, room, target_temp)
        if self._device is None or not self._device.setup_finished:
            raise PlatformNotReady

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
        """Set new target operation mode.
        Switch device on if was previously off"""
        if not self.is_on:
            self._on = True
        if operation_mode == STATE_AUTO:
            self._device.set_temperature_to_auto()
            self._current_operation_mode = operation_mode
            return
        if operation_mode == STATE_MANUAL:
            self._device.set_temperature_to_manual()
            self._current_operation_mode = operation_mode
            return

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
        self._device.update_room()

        # set operation mode
        mode_map = {'prog': STATE_AUTO, 'fixed': STATE_MANUAL}
        self._current_operation_mode = mode_map.get(
            self._device.get_run_mode(), STATE_MANUAL)

        # set whether device is on/off
        if self._device.get_run_mode() == 'off':
            self._on = False
        else:
            self._on = True
