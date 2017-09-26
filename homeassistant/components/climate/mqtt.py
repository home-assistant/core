"""
Support for MQTT climate devices.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.mqtt/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt

from homeassistant.components.climate import (
    STATE_HEAT, STATE_COOL, STATE_DRY, STATE_FAN_ONLY, ClimateDevice,
    PLATFORM_SCHEMA, STATE_AUTO, ATTR_OPERATION_MODE)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, STATE_ON, STATE_OFF, ATTR_TEMPERATURE,
    CONF_NAME)
from homeassistant.components.mqtt import (CONF_QOS, CONF_RETAIN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (async_track_state_change)
from homeassistant.components.fan import (SPEED_LOW, SPEED_MEDIUM,
                                          SPEED_HIGH)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt', 'sensor']

DEFAULT_NAME = 'MQTT HVAC'

CONF_SENSOR = 'target_sensor'
CONF_POWER_COMMAND_TOPIC = 'power_command_topic'
CONF_MODE_COMMAND_TOPIC = 'mode_command_topic'
CONF_TEMPERATURE_COMMAND_TOPIC = 'temperature_command_topic'
CONF_FAN_MODE_COMMAND_TOPIC = 'fan_mode_command_topic'
CONF_SWING_MODE_COMMAND_TOPIC = 'swing_mode_command_topic'
CONF_FAN_MODE_LIST = 'fan_modes'
CONF_MODE_LIST = 'modes'
CONF_SWING_MODE_LIST = 'swing_modes'
CONF_INITIAL = 'initial'
CONF_SEND_IF_OFF = 'send_if_off'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_POWER_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_TEMPERATURE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_FAN_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_SWING_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_FAN_MODE_LIST,
                 default=[STATE_AUTO, SPEED_LOW,
                          SPEED_MEDIUM, SPEED_HIGH]): cv.ensure_list,
    vol.Optional(CONF_SWING_MODE_LIST,
                 default=[STATE_ON, STATE_OFF]): cv.ensure_list,
    vol.Optional(CONF_MODE_LIST,
                 default=[STATE_AUTO, STATE_OFF, STATE_COOL, STATE_HEAT,
                          STATE_DRY, STATE_FAN_ONLY]): cv.ensure_list,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_INITIAL, default=21): cv.positive_int,
    vol.Optional(CONF_SEND_IF_OFF, default=True): cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the MQTT climate devices."""
    async_add_devices([
        MqttClimate(
            hass,
            config.get(CONF_NAME),
            config.get(CONF_SENSOR),
            {
                key: config.get(key) for key in (
                    CONF_POWER_COMMAND_TOPIC,
                    CONF_MODE_COMMAND_TOPIC,
                    CONF_TEMPERATURE_COMMAND_TOPIC,
                    CONF_FAN_MODE_COMMAND_TOPIC,
                    CONF_SWING_MODE_COMMAND_TOPIC,
                )
            },
            config.get(CONF_QOS),
            config.get(CONF_RETAIN),
            config.get(CONF_MODE_LIST),
            config.get(CONF_FAN_MODE_LIST),
            config.get(CONF_SWING_MODE_LIST),
            config.get(CONF_INITIAL),
            None, None, SPEED_LOW,
            STATE_OFF, STATE_OFF, None,
            config.get(CONF_SEND_IF_OFF))
    ])


class MqttClimate(ClimateDevice):
    """Representation of a demo climate device."""

    def __init__(self, hass, name, sensor_entity_id, topic, qos, retain,
                 mode_list, fan_mode_list, swing_mode_list,
                 target_temperature,
                 away, hold, current_fan_mode,
                 current_swing_mode,
                 current_operation, aux, send_if_off):
        """Initialize the climate device."""
        self.hass = hass
        self._name = name
        self._topic = topic
        self._qos = qos
        self._retain = retain
        self._target_temperature = target_temperature
        self._unit_of_measurement = hass.config.units.temperature_unit
        self._away = away
        self._hold = hold
        self._current_temperature = None
        self._current_fan_mode = current_fan_mode
        self._current_operation = current_operation
        self._aux = aux
        self._current_swing_mode = current_swing_mode
        self._fan_list = fan_mode_list
        self._operation_list = mode_list
        self._swing_list = swing_mode_list
        self._target_temperature_step = 1
        self._send_if_off = send_if_off

        @callback
        def async_handle_sensor_changed(entity_id, old_state, new_state):
            """Handle temperature changes."""
            if new_state is None:
                return

            self.update_current_temperature(new_state)
            hass.async_add_job(self.async_update_ha_state)

        async_track_state_change(
            hass, sensor_entity_id, async_handle_sensor_changed)

        # TODO move to 'on added'
        sensor_state = hass.states.get(sensor_entity_id)
        if sensor_state:
            self._async_update_current_temperature(sensor_state)

    def update_current_temperature(self, state):
        """Update thermostat with latest state from sensor."""
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        try:
            self._current_temperature = self.hass.config.units.temperature(
                float(state.state), unit)
        except ValueError as ex:
            _LOGGER.error('Unable to update from sensor: %s', ex)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

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
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._target_temperature_step

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
        """Return true if away mode is on."""
        return self._aux

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    @asyncio.coroutine
    def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_OPERATION_MODE) is not None:
            operation_mode = kwargs.get(ATTR_OPERATION_MODE)
            yield from self.async_set_operation_mode(operation_mode)

        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
            if self._send_if_off or self._current_operation != STATE_OFF:
                mqtt.async_publish(
                    self.hass, self._topic[CONF_TEMPERATURE_COMMAND_TOPIC],
                    self._target_temperature, self._qos, self._retain)

        self.async_schedule_update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        if self._send_if_off or self._current_operation != STATE_OFF:
            mqtt.async_publish(
                self.hass, self._topic[CONF_SWING_MODE_COMMAND_TOPIC],
                swing_mode, self._qos, self._retain)
        self._current_swing_mode = swing_mode
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan):
        """Set new target temperature."""
        if self._send_if_off or self._current_operation != STATE_OFF:
            mqtt.async_publish(
                self.hass, self._topic[CONF_FAN_MODE_COMMAND_TOPIC],
                fan, self._qos, self._retain)
        self._current_fan_mode = fan
        self.schedule_update_ha_state()

    @asyncio.coroutine
    def async_set_operation_mode(self, operation_mode) -> None:
        """Set new operation mode."""
        if self._topic[CONF_POWER_COMMAND_TOPIC] is not None:
            if (self._current_operation == STATE_OFF and
                    operation_mode != STATE_OFF):
                mqtt.async_publish(
                    self.hass, self._topic[CONF_POWER_COMMAND_TOPIC],
                    STATE_ON, self._qos, self._retain)
            elif (self._current_operation != STATE_OFF and
                  operation_mode == STATE_OFF):
                mqtt.async_publish(
                    self.hass, self._topic[CONF_POWER_COMMAND_TOPIC],
                    STATE_OFF, self._qos, self._retain)

        if self._topic[CONF_MODE_COMMAND_TOPIC] is not None:
            mqtt.async_publish(
                self.hass, self._topic[CONF_MODE_COMMAND_TOPIC],
                operation_mode, self._qos, self._retain)

        self._current_operation = operation_mode
        self.hass.async_add_job(self.async_update_ha_state())

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
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
        """Turn away auxillary heater on."""
        self._aux = True
        self.schedule_update_ha_state()

    def turn_aux_heat_off(self):
        """Turn auxillary heater off."""
        self._aux = False
        self.schedule_update_ha_state()
