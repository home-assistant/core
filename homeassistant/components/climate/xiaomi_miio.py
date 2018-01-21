"""
Support for Xiaomi Mi Home Air Conditioner Companion (AC Partner)

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.xiaomi_miio
"""
import logging
import asyncio
from datetime import timedelta
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.climate import (
    PLATFORM_SCHEMA, ClimateDevice, ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW, ATTR_OPERATION_MODE, )
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME, CONF_HOST, CONF_TOKEN, CONF_TIMEOUT, STATE_ON, STATE_OFF,
    STATE_IDLE, )

from homeassistant.helpers.event import (
    async_track_state_change, async_track_time_interval, )
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-miio==0.3.4']

DEPENDENCIES = ['sensor']

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = 'Xiaomi AC Companion'

DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3

DEFAULT_MIN_TMEP = 16
DEFAULT_MAX_TMEP = 30
DEFAULT_STEP = 1

STATE_HEAT = 'heat'
STATE_COOL = 'cool'
STATE_AUTO = 'auto'

STATE_LOW = 'low'
STATE_MEDIUM = 'medium'
STATE_HIGH = 'high'

CONF_SENSOR = 'target_sensor'
# CONF_TARGET_TEMP = 'target_temp'
CONF_SYNC = 'sync'
CONF_CUSTOMIZE = 'customize'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Required(CONF_SENSOR, default=None): cv.entity_id,
    vol.Optional(CONF_CUSTOMIZE, default=None): dict,
    vol.Optional(CONF_SYNC, default=15): cv.positive_int
})


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the air conditioning companion from config."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME) or DEFAULT_NAME
    token = config.get(CONF_TOKEN)
    sensor_entity_id = config.get(CONF_SENSOR)
    # target_temp = config.get(CONF_TARGET_TEMP)
    sync = config.get(CONF_SYNC)
    customize = config.get(CONF_CUSTOMIZE)

    add_devices_callback([XiaomiAirConditioningCompanion(
        hass, name, None, None, None, STATE_AUTO, None,
        STATE_OFF, STATE_OFF, None, DEFAULT_MAX_TMEP, DEFAULT_MIN_TMEP, host,
        token, sensor_entity_id, sync, customize)])


class XiaomiAirConditioningCompanion(ClimateDevice):
    """Representation of a Xiaomi Air Conditioning Companion."""

    # FIXME: Mismatch at the naming of the OperationModes (heating vs. heat)
    # FIXME: OperationMode doesn't return 'off' anymore

    def __init__(self, hass, name, target_humidity,
                 away, hold, current_fan_mode, current_humidity,
                 current_swing_mode, current_operation, aux,
                 target_temp_high, target_temp_low, host,
                 token, sensor_entity_id, sync, customize):

        """Initialize the climate device."""
        self.hass = hass
        self._name = name if name else DEFAULT_NAME
        self._target_humidity = target_humidity
        self._away = away
        self._hold = hold
        self.host = host
        self.token = token
        self.sync = sync
        self._customize = customize

        from miio import AirConditioningCompanion
        _LOGGER.info("initializing with host %s token %s", self.host,
                     self.token)
        self._climate = AirConditioningCompanion(self.host, self.token)

        self._state = None
        # FIXME: Should the state updated here? Currently it's needed later on.
        self._climate.status()

        self._target_temperature = self._state.temperature
        self._current_operation = self._state.operation.name.tolower()

        self._current_humidity = current_humidity
        self._aux = aux
        self._operation_list = [STATE_HEAT, STATE_COOL, STATE_AUTO, STATE_OFF]

        if self._customize and ('fan' in self._customize):
            self._customize_fan_list = list(self._customize['fan'])
            self._fan_list = self._customize_fan_list
            self._current_fan_mode = STATE_IDLE
        else:
            self._fan_list = [STATE_LOW, STATE_MEDIUM, STATE_HIGH, STATE_AUTO]
            self._current_fan_mode = self._state.fan_speed.name.tolower()

        if self._customize and ('swing' in self._customize):
            self._customize_swing_list = list(self._customize['swing'])
            self._swing_list = self._customize_swing_list
            self._current_swing_mode = STATE_IDLE
        else:
            self._swing_list = [STATE_ON, STATE_OFF]
            self._current_swing_mode = \
                STATE_ON if self._state.swing_mode else STATE_OFF
        self._target_temperature_high = target_temp_high
        self._target_temperature_low = target_temp_low
        self._max_temp = target_temp_high + 1
        self._min_temp = target_temp_low - 1
        self._target_temp_step = DEFAULT_STEP

        self._unit_of_measurement = TEMP_CELSIUS
        self._current_temperature = None
        self._sensor_entity_id = sensor_entity_id

        if sensor_entity_id:
            async_track_state_change(
                hass, sensor_entity_id, self._async_sensor_changed)
            sensor_state = hass.states.get(sensor_entity_id)
            if sensor_state:
                self._async_update_temp(sensor_state)
        if sync:
            async_track_time_interval(
                hass, self._async_get_states, timedelta(seconds=self.sync))

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        try:
            self._current_temperature = self.hass.config.units.temperature(
                float(state.state), unit)
            self.schedule_update_ha_state()
        except ValueError as ex:
            _LOGGER.error('Unable to update from sensor: %s', ex)

    @asyncio.coroutine
    def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        if new_state is None:
            return
        self._async_update_temp(new_state)

    @asyncio.coroutine
    def _async_get_states(self, now=None):
        """Update the state of this climate device."""
        self._climate.status()
        self._current_operation = self._state.operation.name.tolower()
        self._target_temperature = self._state.temperature
        if (not self._customize) or (self._customize
                                     and 'fan' not in self._customize):
            self._current_fan_mode = self._state.fan_speed.name.tolower()
        if (not self._customize) or (self._customize
                                     and 'swing' not in self._customize):
            self._current_swing_mode = \
                STATE_ON if self._state.swing_mode else STATE_OFF
        if not self._sensor_entity_id:
            self._current_temperature = self._state.temperature
        _LOGGER.info('Sync climate status, air_condition_model: %s, '
                     'operation: %s, temperature: %s, fan: %s, swing: %s',
                     self._state.air_condition_model,
                     self._state.operation.name.tolower(),
                     self._state.temperature,
                     self._state.fan_speed.name.tolower(),
                     self._state.sweep)
        self.schedule_update_ha_state()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def target_temperature_step(self):
        """Return the target temperature step."""
        return self._target_temp_step

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
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_high(self):
        """Return the upper bound of the target temperature we try to reach."""
        return self._target_temperature_high

    @property
    def target_temperature_low(self):
        """Return the lower bound of the target temperature we try to reach."""
        return self._target_temperature_low

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    @property
    def current_hold_mode(self):
        """Return hold mode setting."""
        return self._hold

    @property
    def is_aux_heat_on(self):
        """Return true if aux heat is on."""
        return self._aux

    @property
    def current_fan_mode(self):
        """Return the current fan mode."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    def set_temperature(self, **kwargs):
        """Set target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)

        if kwargs.get(ATTR_TARGET_TEMP_HIGH) is not None and \
                kwargs.get(ATTR_TARGET_TEMP_LOW) is not None:
            self._target_temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            self._target_temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)

        if kwargs.get(ATTR_OPERATION_MODE) is not None:
            self._current_operation = kwargs.get(ATTR_OPERATION_MODE)
        else:
            if self._target_temperature < self._target_temperature_low:
                self._current_operation = STATE_OFF
                self._target_temperature = self._target_temperature_low
            elif self._target_temperature > self._target_temperature_high:
                self._current_operation = STATE_OFF
                self._target_temperature = self._target_temperature_high
            elif self._current_temperature and (
                            self._current_operation == STATE_OFF or
                            self._current_operation == STATE_IDLE):
                self._current_operation = STATE_AUTO

        self.send_configuration()
        self.schedule_update_ha_state()

    def set_humidity(self, humidity):
        """Set the target humidity."""
        self._target_humidity = humidity
        self.schedule_update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set target temperature."""
        self._current_swing_mode = swing_mode
        if self._customize and ('swing' in self._customize) and (self._current_swing_mode in self._customize['swing']):
            self.send_custom_command(self._customize['swing'][self._current_swing_mode])
        else:
            self.send_configuration()
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan):
        """Set the fan mode."""
        self._current_fan_mode = fan
        if self._customize and ('fan' in self._customize) and (self._current_fan_mode in self._customize['fan']):
            self.send_custom_command(self._customize['fan'][self._current_fan_mode])
        else:
            self.send_configuration()
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        self._current_operation = operation_mode
        self.send_configuration()
        self.schedule_update_ha_state()

    @property
    def current_swing_mode(self):
        """Return the current swing setting."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self.schedule_update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self.schedule_update_ha_state()

    def set_hold_mode(self, hold):
        """Update hold mode on."""
        self._hold = hold
        self.schedule_update_ha_state()

    def turn_aux_heat_on(self):
        """Turn auxillary heater on."""
        self._aux = True
        self.schedule_update_ha_state()

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self._aux = False
        self.schedule_update_ha_state()

    def send_configuration(self):
        try:
            self._climate.send_configuration(
                self._state.air_condition_model,
                self._state.power,
                self._current_operation,
                self._target_temperature,
                self._current_fan_mode,
                self._current_swing_mode)
            _LOGGER.info('Climate device configuration updated.')
        except ValueError as ex:
            _LOGGER.error('Climate device configuration update failed: %s', ex)

    def send_custom_command(self, command: str):
        try:
            if command[0:2] == "01":
                self._climate.send_command(command)
            else:
                self._climate.send_ir_code(command)
            _LOGGER.info('Climate device configuration updated.')
        except ValueError as ex:
            _LOGGER.error('Climate device configuration update failed: %s', ex)
