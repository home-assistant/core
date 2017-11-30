"""
Adds support for generic thermostat units.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.generic_thermostat/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import switch
from homeassistant.components.climate import (
    STATE_HEAT, STATE_COOL, STATE_IDLE, ClimateDevice, PLATFORM_SCHEMA,
    STATE_AUTO)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, STATE_ON, STATE_OFF, ATTR_TEMPERATURE,
    CONF_NAME)
from homeassistant.helpers import condition
from homeassistant.helpers.event import (
    async_track_state_change, async_track_time_interval)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['switch', 'sensor']

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = 'Generic Thermostat'

CONF_HEATER = 'heater'
CONF_SENSOR = 'target_sensor'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_TARGET_TEMP = 'target_temp'
CONF_AC_MODE = 'ac_mode'
CONF_MIN_DUR = 'min_cycle_duration'
CONF_COLD_TOLERANCE = 'cold_tolerance'
CONF_HOT_TOLERANCE = 'hot_tolerance'
CONF_KEEP_ALIVE = 'keep_alive'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HEATER): cv.entity_id,
    vol.Required(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_AC_MODE): cv.boolean,
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_DUR): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(
        float),
    vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(
        float),
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
    vol.Optional(CONF_KEEP_ALIVE): vol.All(
        cv.time_period, cv.positive_timedelta),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the generic thermostat platform."""
    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER)
    sensor_entity_id = config.get(CONF_SENSOR)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_temp = config.get(CONF_TARGET_TEMP)
    ac_mode = config.get(CONF_AC_MODE)
    min_cycle_duration = config.get(CONF_MIN_DUR)
    cold_tolerance = config.get(CONF_COLD_TOLERANCE)
    hot_tolerance = config.get(CONF_HOT_TOLERANCE)
    keep_alive = config.get(CONF_KEEP_ALIVE)

    async_add_devices([GenericThermostat(
        hass, name, heater_entity_id, sensor_entity_id, min_temp, max_temp,
        target_temp, ac_mode, min_cycle_duration, cold_tolerance,
        hot_tolerance, keep_alive)])


class GenericThermostat(ClimateDevice):
    """Representation of a Generic Thermostat device."""

    def __init__(self, hass, name, heater_entity_id, sensor_entity_id,
                 min_temp, max_temp, target_temp, ac_mode, min_cycle_duration,
                 cold_tolerance, hot_tolerance, keep_alive):
        """Initialize the thermostat."""
        self.hass = hass
        self._name = name
        self.heater_entity_id = heater_entity_id
        self.ac_mode = ac_mode
        self.min_cycle_duration = min_cycle_duration
        self._cold_tolerance = cold_tolerance
        self._hot_tolerance = hot_tolerance
        self._keep_alive = keep_alive
        self._enabled = True

        self._active = False
        self._cur_temp = None
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temp = target_temp
        self._unit = hass.config.units.temperature_unit

        async_track_state_change(
            hass, sensor_entity_id, self._async_sensor_changed)
        async_track_state_change(
            hass, heater_entity_id, self._async_switch_changed)

        if self._keep_alive:
            async_track_time_interval(
                hass, self._async_keep_alive, self._keep_alive)

        sensor_state = hass.states.get(sensor_entity_id)
        if sensor_state:
            self._async_update_temp(sensor_state)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if not self._enabled:
            return STATE_OFF
        if self.ac_mode:
            cooling = self._active and self._is_device_active
            return STATE_COOL if cooling else STATE_IDLE

        heating = self._active and self._is_device_active
        return STATE_HEAT if heating else STATE_IDLE

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def operation_list(self):
        """List of available operation modes."""
        return [STATE_AUTO, STATE_OFF]

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if operation_mode == STATE_AUTO:
            self._enabled = True
            self._async_control_heating()
        elif operation_mode == STATE_OFF:
            self._enabled = False
            if self._is_device_active:
                switch.async_turn_off(self.hass, self.heater_entity_id)
        else:
            _LOGGER.error('Unrecognized operation mode: %s', operation_mode)
            return
        # Ensure we updae the current operation after changing the mode
        self.schedule_update_ha_state()

    @asyncio.coroutine
    def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = temperature
        self._async_control_heating()
        yield from self.async_update_ha_state()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        # pylint: disable=no-member
        if self._min_temp:
            return self._min_temp

        # get default temp from super class
        return ClimateDevice.min_temp.fget(self)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        # pylint: disable=no-member
        if self._max_temp:
            return self._max_temp

        # Get default temp from super class
        return ClimateDevice.max_temp.fget(self)

    @asyncio.coroutine
    def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        if new_state is None:
            return

        self._async_update_temp(new_state)
        self._async_control_heating()
        yield from self.async_update_ha_state()

    @callback
    def _async_switch_changed(self, entity_id, old_state, new_state):
        """Handle heater switch state changes."""
        if new_state is None:
            return
        self.async_schedule_update_ha_state()

    @callback
    def _async_keep_alive(self, time):
        """Call at constant intervals for keep-alive purposes."""
        if self.current_operation in [STATE_COOL, STATE_HEAT]:
            switch.async_turn_on(self.hass, self.heater_entity_id)
        else:
            switch.async_turn_off(self.hass, self.heater_entity_id)

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        try:
            self._cur_temp = self.hass.config.units.temperature(
                float(state.state), unit)
        except ValueError as ex:
            _LOGGER.error('Unable to update from sensor: %s', ex)

    @callback
    def _async_control_heating(self):
        """Check if we need to turn heating on or off."""
        if not self._active and None not in (self._cur_temp,
                                             self._target_temp):
            self._active = True
            _LOGGER.info('Obtained current and target temperature. '
                         'Generic thermostat active.')

        if not self._active:
            return

        if not self._enabled:
            return

        if self.min_cycle_duration:
            if self._is_device_active:
                current_state = STATE_ON
            else:
                current_state = STATE_OFF
            long_enough = condition.state(
                self.hass, self.heater_entity_id, current_state,
                self.min_cycle_duration)
            if not long_enough:
                return

        if self.ac_mode:
            is_cooling = self._is_device_active
            if is_cooling:
                too_cold = self._target_temp - self._cur_temp >= \
                    self._cold_tolerance
                if too_cold:
                    _LOGGER.info('Turning off AC %s', self.heater_entity_id)
                    switch.async_turn_off(self.hass, self.heater_entity_id)
            else:
                too_hot = self._cur_temp - self._target_temp >= \
                    self._hot_tolerance
                if too_hot:
                    _LOGGER.info('Turning on AC %s', self.heater_entity_id)
                    switch.async_turn_on(self.hass, self.heater_entity_id)
        else:
            is_heating = self._is_device_active
            if is_heating:
                too_hot = self._cur_temp - self._target_temp >= \
                    self._hot_tolerance
                if too_hot:
                    _LOGGER.info('Turning off heater %s',
                                 self.heater_entity_id)
                    switch.async_turn_off(self.hass, self.heater_entity_id)
            else:
                too_cold = self._target_temp - self._cur_temp >= \
                    self._cold_tolerance
                if too_cold:
                    _LOGGER.info('Turning on heater %s', self.heater_entity_id)
                    switch.async_turn_on(self.hass, self.heater_entity_id)

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        return switch.is_on(self.hass, self.heater_entity_id)
