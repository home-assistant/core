"""
Adds support for heat control units.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.heat_control/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util as util
from homeassistant.components import switch
from homeassistant.components.thermostat import (
    STATE_HEAT, STATE_IDLE, ThermostatDevice)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.event import track_state_change

DEPENDENCIES = ['switch', 'sensor']

TOL_TEMP = 0.3

CONF_NAME = 'name'
DEFAULT_NAME = 'Heat Control'
CONF_HEATER = 'heater'
CONF_SENSOR = 'target_sensor'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_TARGET_TEMP = 'target_temp'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required("platform"): "heat_control",
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HEATER): cv.entity_id,
    vol.Required(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the heat control thermostat."""
    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER)
    sensor_entity_id = config.get(CONF_SENSOR)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_temp = config.get(CONF_TARGET_TEMP)

    add_devices([HeatControl(hass, name, heater_entity_id, sensor_entity_id,
                             min_temp, max_temp, target_temp)])


# pylint: disable=too-many-instance-attributes
class HeatControl(ThermostatDevice):
    """Representation of a HeatControl device."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, name, heater_entity_id, sensor_entity_id,
                 min_temp, max_temp, target_temp):
        """Initialize the thermostat."""
        self.hass = hass
        self._name = name
        self.heater_entity_id = heater_entity_id

        self._active = False
        self._cur_temp = None
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temp = target_temp
        self._unit = None

        track_state_change(hass, sensor_entity_id, self._sensor_changed)

        sensor_state = hass.states.get(sensor_entity_id)
        if sensor_state:
            self._update_temp(sensor_state)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def operation(self):
        """Return current operation ie. heat, cool, idle."""
        return STATE_HEAT if self._active and self._is_heating else STATE_IDLE

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    def set_temperature(self, temperature):
        """Set new target temperature."""
        self._target_temp = temperature
        self._control_heating()
        self.update_ha_state()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        # pylint: disable=no-member
        if self._min_temp:
            return self._min_temp
        else:
            # get default temp from super class
            return ThermostatDevice.min_temp.fget(self)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        # pylint: disable=no-member
        if self._min_temp:
            return self._max_temp
        else:
            # Get default temp from super class
            return ThermostatDevice.max_temp.fget(self)

    def _sensor_changed(self, entity_id, old_state, new_state):
        """Called when temperature changes."""
        if new_state is None:
            return

        self._update_temp(new_state)
        self._control_heating()
        self.update_ha_state()

    def _update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if unit not in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
            self._cur_temp = None
            self._unit = None
            _LOGGER.error('Sensor has unsupported unit: %s (allowed: %s, %s)',
                          unit, TEMP_CELSIUS, TEMP_FAHRENHEIT)
            return

        temp = util.convert(state.state, float)

        if temp is None:
            self._cur_temp = None
            self._unit = None
            _LOGGER.error('Unable to parse sensor temperature: %s',
                          state.state)
            return

        self._cur_temp = temp
        self._unit = unit

    def _control_heating(self):
        """Check if we need to turn heating on or off."""
        if not self._active and None not in (self._cur_temp,
                                             self._target_temp):
            self._active = True
            _LOGGER.info('Obtained current and target temperature. '
                         'Heat control active.')

        if not self._active:
            return

        too_cold = self._target_temp - self._cur_temp > TOL_TEMP
        is_heating = self._is_heating

        if too_cold and not is_heating:
            _LOGGER.info('Turning on heater %s', self.heater_entity_id)
            switch.turn_on(self.hass, self.heater_entity_id)
        elif not too_cold and is_heating:
            _LOGGER.info('Turning off heater %s', self.heater_entity_id)
            switch.turn_off(self.hass, self.heater_entity_id)

    @property
    def _is_heating(self):
        """If the heater is currently heating."""
        return switch.is_on(self.hass, self.heater_entity_id)
