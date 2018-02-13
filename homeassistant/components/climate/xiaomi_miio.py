"""
Support for Xiaomi Mi Home Air Conditioner Companion (AC Partner)

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.xiaomi_miio
"""
import logging
import asyncio
from functools import partial
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

from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-miio==0.3.5']

DEPENDENCIES = ['sensor']

SUCCESS = ['ok']

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = 'Xiaomi AC Companion'

DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3

DEFAULT_MIN_TEMP = 16
DEFAULT_MAX_TEMP = 30
DEFAULT_STEP = 1

STATE_HEAT = 'heat'
STATE_COOL = 'cool'
STATE_AUTO = 'auto'

STATE_LOW = 'low'
STATE_MEDIUM = 'medium'
STATE_HIGH = 'high'

ATTR_AIR_CONDITION_MODEL = 'ac_model'
ATTR_AIR_CONDITION_POWER = 'ac_power'
ATTR_SWING_MODE = 'swing_mode'
ATTR_FAN_SPEED = 'fan_speed'

DEFAULT_OPERATION_MODES = [STATE_HEAT, STATE_COOL, STATE_AUTO, STATE_OFF]
DEFAULT_SWING_MODES = [STATE_ON, STATE_OFF]
DEFAULT_FAN_MODES = [STATE_LOW, STATE_MEDIUM, STATE_HIGH, STATE_AUTO]

CONF_SENSOR = 'target_sensor'
CONF_CUSTOMIZE = 'customize'

SCAN_INTERVAL = timedelta(seconds=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Required(CONF_SENSOR, default=None): cv.entity_id,
    vol.Optional(CONF_CUSTOMIZE, default=None): dict,
})


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the air conditioning companion from config."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME) or DEFAULT_NAME
    token = config.get(CONF_TOKEN)
    sensor_entity_id = config.get(CONF_SENSOR)
    customize = config.get(CONF_CUSTOMIZE)

    async_add_devices([XiaomiAirConditioningCompanion(
        hass, name, host, token, sensor_entity_id, customize)],
        update_before_add=True)


class XiaomiAirConditioningCompanion(ClimateDevice):
    """Representation of a Xiaomi Air Conditioning Companion."""

    def __init__(self, hass, name, host, token, sensor_entity_id, customize):

        """Initialize the climate device."""
        self.hass = hass
        self._state = None
        self._state_attrs = {
            ATTR_AIR_CONDITION_MODEL: None,
            ATTR_AIR_CONDITION_POWER: None,
            ATTR_TEMPERATURE: None,
            ATTR_SWING_MODE: None,
            ATTR_FAN_SPEED: None,
            ATTR_OPERATION_MODE: None,
        }

        self._name = name if name else DEFAULT_NAME
        self._unit_of_measurement = TEMP_CELSIUS
        self._host = host
        self._token = token
        self._sensor_entity_id = sensor_entity_id
        self._customize = customize

        self._target_temperature = None
        self._target_humidity = None
        self._current_temperature = None
        self._current_humidity = None
        self._current_swing_mode = None
        self._current_operation = None
        self._current_fan_mode = None

        self._operation_list = DEFAULT_OPERATION_MODES
        self._away = None
        self._hold = None
        self._aux = None
        self._target_temperature_high = DEFAULT_MAX_TEMP
        self._target_temperature_low = DEFAULT_MIN_TEMP
        self._max_temp = DEFAULT_MAX_TEMP + 1
        self._min_temp = DEFAULT_MIN_TEMP - 1
        self._target_temp_step = DEFAULT_STEP

        if self._customize and ('fan' in self._customize):
            self._customize_fan_list = list(self._customize['fan'])
            self._fan_list = self._customize_fan_list
        else:
            self._fan_list = DEFAULT_FAN_MODES

        if self._customize and ('swing' in self._customize):
            self._customize_swing_list = list(self._customize['swing'])
            self._swing_list = self._customize_swing_list
        else:
            self._swing_list = DEFAULT_SWING_MODES

        if sensor_entity_id:
            async_track_state_change(
                hass, sensor_entity_id, self._async_sensor_changed)
            sensor_state = hass.states.get(sensor_entity_id)
            if sensor_state:
                self._async_update_temp(sensor_state)

        from miio import AirConditioningCompanion
        _LOGGER.info("initializing with host %s token %s", self._host,
                     self._token)
        self._climate = AirConditioningCompanion(self._host, self._token)

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        try:
            self._current_temperature = self.hass.config.units.temperature(
                float(state.state), unit)
        except ValueError as ex:
            _LOGGER.error('Unable to update from sensor: %s', ex)

    @asyncio.coroutine
    def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        if new_state is None:
            return
        self._async_update_temp(new_state)

    @asyncio.coroutine
    def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a AC companion command handling error messages."""
        from miio import DeviceException
        try:
            result = yield from self.hass.async_add_job(
                partial(func, *args, **kwargs))

            _LOGGER.debug("Response received: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    @asyncio.coroutine
    def async_update(self):
        """Update the state of this climate device."""
        from miio import DeviceException

        try:
            state = yield from self.hass.async_add_job(self._climate.status)
            _LOGGER.debug("Got new state: %s", state)

            self._state = state.is_on
            self._state_attrs = {
                ATTR_AIR_CONDITION_MODEL: state.air_condition_model,
                ATTR_AIR_CONDITION_POWER: state.air_condition_power,
                ATTR_TEMPERATURE: state.temperature,
                ATTR_SWING_MODE: state.swing_mode.name,
                ATTR_FAN_SPEED: state.fan_speed.name,
                ATTR_OPERATION_MODE: state.operation_mode.name,
            }

            self._current_operation = state.operation.name.lower()
            # BUG? The target_temperature shoudn't be updated here
            # self._target_temperature = state.temperature

            if (not self._customize) or (self._customize
                                         and 'fan' not in self._customize):
                self._current_fan_mode = state.fan_speed.name.lower()

            if (not self._customize) or (self._customize
                                         and 'swing' not in self._customize):
                self._current_swing_mode = \
                    STATE_ON if state.swing_mode else STATE_OFF

            if not self._sensor_entity_id:
                self._current_temperature = state.temperature

        except DeviceException as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)

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

    @asyncio.coroutine
    def async_set_temperature(self, **kwargs):
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

        self._send_configuration()

    @asyncio.coroutine
    def async_set_humidity(self, humidity):
        """Set the target humidity."""
        self._target_humidity = humidity

    @asyncio.coroutine
    def async_set_swing_mode(self, swing_mode):
        """Set target temperature."""
        self._current_swing_mode = swing_mode
        if self._customize and ('swing' in self._customize) and \
                (self._current_swing_mode in self._customize['swing']):
            self._send_custom_command(
                self._customize['swing'][self._current_swing_mode])
        else:
            self._send_configuration()

    @asyncio.coroutine
    def async_set_fan_mode(self, fan):
        """Set the fan mode."""
        self._current_fan_mode = fan
        if self._customize and ('fan' in self._customize) and \
                (self._current_fan_mode in self._customize['fan']):
            self._send_custom_command(
                self._customize['fan'][self._current_fan_mode])
        else:
            self._send_configuration()

    @asyncio.coroutine
    def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        self._current_operation = operation_mode
        self._send_configuration()

    @property
    def current_swing_mode(self):
        """Return the current swing setting."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    @asyncio.coroutine
    def async_turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True

    @asyncio.coroutine
    def async_turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False

    @asyncio.coroutine
    def async_set_hold_mode(self, hold):
        """Update hold mode on."""
        self._hold = hold

    @asyncio.coroutine
    def async_turn_aux_heat_on(self):
        """Turn auxillary heater on."""
        self._aux = True

    @asyncio.coroutine
    def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self._aux = False

    def _send_configuration(self):
        from miio.airconditioningcompanion import \
            Power, OperationMode, FanSpeed, SwingMode

        if ATTR_AIR_CONDITION_MODEL in self._state_attrs:
            yield from self._try_command(
                "Sending new air conditioner configuration failed.",
                self._climate.send_configuration(
                    self._state_attrs[ATTR_AIR_CONDITION_MODEL],
                    Power(int(self._state)),
                    OperationMode[self._current_operation.title()],
                    self._target_temperature,
                    FanSpeed[self._current_fan_mode.title()],
                    SwingMode[self._current_swing_mode.title()]
                ), False)
        else:
            _LOGGER.error('Model number of the air condition unknown. '
                          'Configuration cannot be sent.')

    def _send_custom_command(self, command: str):
        if command[0:2] == "01":
            yield from self._try_command(
                "Sending new air conditioner configuration failed.",
                self._climate.send_command(command), False)
        else:
            yield from self._try_command(
                "Sending new air conditioner configuration failed.",
                self._climate.send_ir_code(command), False)
