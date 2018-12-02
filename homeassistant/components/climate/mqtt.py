"""
Support for MQTT climate devices.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import mqtt, climate

from homeassistant.components.climate import (
    STATE_HEAT, STATE_COOL, STATE_DRY, STATE_FAN_ONLY, ClimateDevice,
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA, STATE_AUTO,
    ATTR_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE,
    SUPPORT_SWING_MODE, SUPPORT_FAN_MODE, SUPPORT_AWAY_MODE, SUPPORT_HOLD_MODE,
    SUPPORT_AUX_HEAT, DEFAULT_MIN_TEMP, DEFAULT_MAX_TEMP)
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_TEMPERATURE, CONF_NAME, CONF_VALUE_TEMPLATE)
from homeassistant.components.mqtt import (
    ATTR_DISCOVERY_HASH, CONF_AVAILABILITY_TOPIC, CONF_QOS, CONF_RETAIN,
    CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE,
    MQTT_BASE_PLATFORM_SCHEMA, MqttAvailability, MqttDiscoveryUpdate,
    subscription)
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.components.fan import (SPEED_LOW, SPEED_MEDIUM,
                                          SPEED_HIGH)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

DEFAULT_NAME = 'MQTT HVAC'

CONF_POWER_COMMAND_TOPIC = 'power_command_topic'
CONF_POWER_STATE_TOPIC = 'power_state_topic'
CONF_POWER_STATE_TEMPLATE = 'power_state_template'
CONF_MODE_COMMAND_TOPIC = 'mode_command_topic'
CONF_MODE_STATE_TOPIC = 'mode_state_topic'
CONF_MODE_STATE_TEMPLATE = 'mode_state_template'
CONF_TEMPERATURE_COMMAND_TOPIC = 'temperature_command_topic'
CONF_TEMPERATURE_STATE_TOPIC = 'temperature_state_topic'
CONF_TEMPERATURE_STATE_TEMPLATE = 'temperature_state_template'
CONF_FAN_MODE_COMMAND_TOPIC = 'fan_mode_command_topic'
CONF_FAN_MODE_STATE_TOPIC = 'fan_mode_state_topic'
CONF_FAN_MODE_STATE_TEMPLATE = 'fan_mode_state_template'
CONF_SWING_MODE_COMMAND_TOPIC = 'swing_mode_command_topic'
CONF_SWING_MODE_STATE_TOPIC = 'swing_mode_state_topic'
CONF_SWING_MODE_STATE_TEMPLATE = 'swing_mode_state_template'
CONF_AWAY_MODE_COMMAND_TOPIC = 'away_mode_command_topic'
CONF_AWAY_MODE_STATE_TOPIC = 'away_mode_state_topic'
CONF_AWAY_MODE_STATE_TEMPLATE = 'away_mode_state_template'
CONF_HOLD_COMMAND_TOPIC = 'hold_command_topic'
CONF_HOLD_STATE_TOPIC = 'hold_state_topic'
CONF_HOLD_STATE_TEMPLATE = 'hold_state_template'
CONF_AUX_COMMAND_TOPIC = 'aux_command_topic'
CONF_AUX_STATE_TOPIC = 'aux_state_topic'
CONF_AUX_STATE_TEMPLATE = 'aux_state_template'

CONF_CURRENT_TEMPERATURE_TEMPLATE = 'current_temperature_template'
CONF_CURRENT_TEMPERATURE_TOPIC = 'current_temperature_topic'

CONF_PAYLOAD_ON = 'payload_on'
CONF_PAYLOAD_OFF = 'payload_off'

CONF_FAN_MODE_LIST = 'fan_modes'
CONF_MODE_LIST = 'modes'
CONF_SWING_MODE_LIST = 'swing_modes'
CONF_INITIAL = 'initial'
CONF_SEND_IF_OFF = 'send_if_off'

CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_TEMP_STEP = 'temp_step'

TEMPLATE_KEYS = (
    CONF_POWER_STATE_TEMPLATE,
    CONF_MODE_STATE_TEMPLATE,
    CONF_TEMPERATURE_STATE_TEMPLATE,
    CONF_FAN_MODE_STATE_TEMPLATE,
    CONF_SWING_MODE_STATE_TEMPLATE,
    CONF_AWAY_MODE_STATE_TEMPLATE,
    CONF_HOLD_STATE_TEMPLATE,
    CONF_AUX_STATE_TEMPLATE,
    CONF_CURRENT_TEMPERATURE_TEMPLATE
)

SCHEMA_BASE = CLIMATE_PLATFORM_SCHEMA.extend(MQTT_BASE_PLATFORM_SCHEMA.schema)
PLATFORM_SCHEMA = SCHEMA_BASE.extend({
    vol.Optional(CONF_POWER_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_TEMPERATURE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_FAN_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_SWING_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_AWAY_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_HOLD_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_AUX_COMMAND_TOPIC): mqtt.valid_publish_topic,

    vol.Optional(CONF_POWER_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_TEMPERATURE_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_FAN_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_SWING_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_AWAY_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_HOLD_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_AUX_STATE_TOPIC): mqtt.valid_subscribe_topic,

    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_POWER_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_MODE_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_TEMPERATURE_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_FAN_MODE_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_SWING_MODE_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_AWAY_MODE_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_HOLD_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_AUX_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_CURRENT_TEMPERATURE_TEMPLATE): cv.template,

    vol.Optional(CONF_CURRENT_TEMPERATURE_TOPIC):
        mqtt.valid_subscribe_topic,
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
    vol.Optional(CONF_PAYLOAD_ON, default="ON"): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default="OFF"): cv.string,

    vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_TEMP_STEP, default=1.0): vol.Coerce(float)

}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT climate device through configuration.yaml."""
    await _async_setup_entity(hass, config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT climate device dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT climate device."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_payload[ATTR_DISCOVERY_HASH])

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(climate.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT climate devices."""
    async_add_entities([
        MqttClimate(
            hass,
            config,
            discovery_hash,
        )])


class MqttClimate(MqttAvailability, MqttDiscoveryUpdate, ClimateDevice):
    """Representation of an MQTT climate device."""

    def __init__(self, hass, config, discovery_hash):
        """Initialize the climate device."""
        self._config = config
        self._sub_state = None

        self.hass = hass
        self._topic = None
        self._value_templates = None
        self._target_temperature = None
        self._current_fan_mode = None
        self._current_operation = None
        self._current_swing_mode = None
        self._unit_of_measurement = hass.config.units.temperature_unit
        self._away = False
        self._hold = None
        self._current_temperature = None
        self._aux = False

        self._setup_from_config(config)

        availability_topic = config.get(CONF_AVAILABILITY_TOPIC)
        payload_available = config.get(CONF_PAYLOAD_AVAILABLE)
        payload_not_available = config.get(CONF_PAYLOAD_NOT_AVAILABLE)
        qos = config.get(CONF_QOS)

        MqttAvailability.__init__(self, availability_topic, qos,
                                  payload_available, payload_not_available)
        MqttDiscoveryUpdate.__init__(self, discovery_hash,
                                     self.discovery_update)

    async def async_added_to_hass(self):
        """Handle being added to home assistant."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA(discovery_payload)
        self._config = config
        self._setup_from_config(config)
        await self.availability_discovery_update(config)
        await self._subscribe_topics()
        self.async_schedule_update_ha_state()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._topic = {
            key: config.get(key) for key in (
                CONF_POWER_COMMAND_TOPIC,
                CONF_MODE_COMMAND_TOPIC,
                CONF_TEMPERATURE_COMMAND_TOPIC,
                CONF_FAN_MODE_COMMAND_TOPIC,
                CONF_SWING_MODE_COMMAND_TOPIC,
                CONF_AWAY_MODE_COMMAND_TOPIC,
                CONF_HOLD_COMMAND_TOPIC,
                CONF_AUX_COMMAND_TOPIC,
                CONF_POWER_STATE_TOPIC,
                CONF_MODE_STATE_TOPIC,
                CONF_TEMPERATURE_STATE_TOPIC,
                CONF_FAN_MODE_STATE_TOPIC,
                CONF_SWING_MODE_STATE_TOPIC,
                CONF_AWAY_MODE_STATE_TOPIC,
                CONF_HOLD_STATE_TOPIC,
                CONF_AUX_STATE_TOPIC,
                CONF_CURRENT_TEMPERATURE_TOPIC
            )
        }

        # set to None in non-optimistic mode
        self._target_temperature = self._current_fan_mode = \
            self._current_operation = self._current_swing_mode = None
        if self._topic[CONF_TEMPERATURE_STATE_TOPIC] is None:
            self._target_temperature = config.get(CONF_INITIAL)
        if self._topic[CONF_FAN_MODE_STATE_TOPIC] is None:
            self._current_fan_mode = SPEED_LOW
        if self._topic[CONF_SWING_MODE_STATE_TOPIC] is None:
            self._current_swing_mode = STATE_OFF
        if self._topic[CONF_MODE_STATE_TOPIC] is None:
            self._current_operation = STATE_OFF
        self._away = False
        self._hold = None
        self._aux = False

        value_templates = {}
        if CONF_VALUE_TEMPLATE in config:
            value_template = config.get(CONF_VALUE_TEMPLATE)
            value_template.hass = self.hass
            value_templates = {key: value_template for key in TEMPLATE_KEYS}
        for key in TEMPLATE_KEYS & config.keys():
            value_templates[key] = config.get(key)
            value_templates[key].hass = self.hass
        self._value_templates = value_templates

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}
        qos = self._config.get(CONF_QOS)

        @callback
        def handle_current_temp_received(topic, payload, qos):
            """Handle current temperature coming via MQTT."""
            if CONF_CURRENT_TEMPERATURE_TEMPLATE in self._value_templates:
                payload =\
                  self._value_templates[CONF_CURRENT_TEMPERATURE_TEMPLATE].\
                  async_render_with_possible_json_value(payload)

            try:
                self._current_temperature = float(payload)
                self.async_schedule_update_ha_state()
            except ValueError:
                _LOGGER.error("Could not parse temperature from %s", payload)

        if self._topic[CONF_CURRENT_TEMPERATURE_TOPIC] is not None:
            topics[CONF_CURRENT_TEMPERATURE_TOPIC] = {
                'topic': self._topic[CONF_CURRENT_TEMPERATURE_TOPIC],
                'msg_callback': handle_current_temp_received,
                'qos': qos}

        @callback
        def handle_mode_received(topic, payload, qos):
            """Handle receiving mode via MQTT."""
            if CONF_MODE_STATE_TEMPLATE in self._value_templates:
                payload = self._value_templates[CONF_MODE_STATE_TEMPLATE].\
                  async_render_with_possible_json_value(payload)

            if payload not in self._config.get(CONF_MODE_LIST):
                _LOGGER.error("Invalid mode: %s", payload)
            else:
                self._current_operation = payload
                self.async_schedule_update_ha_state()

        if self._topic[CONF_MODE_STATE_TOPIC] is not None:
            topics[CONF_MODE_STATE_TOPIC] = {
                'topic': self._topic[CONF_MODE_STATE_TOPIC],
                'msg_callback': handle_mode_received,
                'qos': qos}

        @callback
        def handle_temperature_received(topic, payload, qos):
            """Handle target temperature coming via MQTT."""
            if CONF_TEMPERATURE_STATE_TEMPLATE in self._value_templates:
                payload = \
                  self._value_templates[CONF_TEMPERATURE_STATE_TEMPLATE].\
                  async_render_with_possible_json_value(payload)

            try:
                self._target_temperature = float(payload)
                self.async_schedule_update_ha_state()
            except ValueError:
                _LOGGER.error("Could not parse temperature from %s", payload)

        if self._topic[CONF_TEMPERATURE_STATE_TOPIC] is not None:
            topics[CONF_TEMPERATURE_STATE_TOPIC] = {
                'topic': self._topic[CONF_TEMPERATURE_STATE_TOPIC],
                'msg_callback': handle_temperature_received,
                'qos': qos}

        @callback
        def handle_fan_mode_received(topic, payload, qos):
            """Handle receiving fan mode via MQTT."""
            if CONF_FAN_MODE_STATE_TEMPLATE in self._value_templates:
                payload = \
                  self._value_templates[CONF_FAN_MODE_STATE_TEMPLATE].\
                  async_render_with_possible_json_value(payload)

            if payload not in self._config.get(CONF_FAN_MODE_LIST):
                _LOGGER.error("Invalid fan mode: %s", payload)
            else:
                self._current_fan_mode = payload
                self.async_schedule_update_ha_state()

        if self._topic[CONF_FAN_MODE_STATE_TOPIC] is not None:
            topics[CONF_FAN_MODE_STATE_TOPIC] = {
                'topic': self._topic[CONF_FAN_MODE_STATE_TOPIC],
                'msg_callback': handle_fan_mode_received,
                'qos': qos}

        @callback
        def handle_swing_mode_received(topic, payload, qos):
            """Handle receiving swing mode via MQTT."""
            if CONF_SWING_MODE_STATE_TEMPLATE in self._value_templates:
                payload = \
                  self._value_templates[CONF_SWING_MODE_STATE_TEMPLATE].\
                  async_render_with_possible_json_value(payload)

            if payload not in self._config.get(CONF_SWING_MODE_LIST):
                _LOGGER.error("Invalid swing mode: %s", payload)
            else:
                self._current_swing_mode = payload
                self.async_schedule_update_ha_state()

        if self._topic[CONF_SWING_MODE_STATE_TOPIC] is not None:
            topics[CONF_SWING_MODE_STATE_TOPIC] = {
                'topic': self._topic[CONF_SWING_MODE_STATE_TOPIC],
                'msg_callback': handle_swing_mode_received,
                'qos': qos}

        @callback
        def handle_away_mode_received(topic, payload, qos):
            """Handle receiving away mode via MQTT."""
            payload_on = self._config.get(CONF_PAYLOAD_ON)
            payload_off = self._config.get(CONF_PAYLOAD_OFF)
            if CONF_AWAY_MODE_STATE_TEMPLATE in self._value_templates:
                payload = \
                  self._value_templates[CONF_AWAY_MODE_STATE_TEMPLATE].\
                  async_render_with_possible_json_value(payload)
                if payload == "True":
                    payload = payload_on
                elif payload == "False":
                    payload = payload_off

            if payload == payload_on:
                self._away = True
            elif payload == payload_off:
                self._away = False
            else:
                _LOGGER.error("Invalid away mode: %s", payload)

            self.async_schedule_update_ha_state()

        if self._topic[CONF_AWAY_MODE_STATE_TOPIC] is not None:
            topics[CONF_AWAY_MODE_STATE_TOPIC] = {
                'topic': self._topic[CONF_AWAY_MODE_STATE_TOPIC],
                'msg_callback': handle_away_mode_received,
                'qos': qos}

        @callback
        def handle_aux_mode_received(topic, payload, qos):
            """Handle receiving aux mode via MQTT."""
            payload_on = self._config.get(CONF_PAYLOAD_ON)
            payload_off = self._config.get(CONF_PAYLOAD_OFF)
            if CONF_AUX_STATE_TEMPLATE in self._value_templates:
                payload = self._value_templates[CONF_AUX_STATE_TEMPLATE].\
                  async_render_with_possible_json_value(payload)
                if payload == "True":
                    payload = payload_on
                elif payload == "False":
                    payload = payload_off

            if payload == payload_on:
                self._aux = True
            elif payload == payload_off:
                self._aux = False
            else:
                _LOGGER.error("Invalid aux mode: %s", payload)

            self.async_schedule_update_ha_state()

        if self._topic[CONF_AUX_STATE_TOPIC] is not None:
            topics[CONF_AUX_STATE_TOPIC] = {
                'topic': self._topic[CONF_AUX_STATE_TOPIC],
                'msg_callback': handle_aux_mode_received,
                'qos': qos}

        @callback
        def handle_hold_mode_received(topic, payload, qos):
            """Handle receiving hold mode via MQTT."""
            if CONF_HOLD_STATE_TEMPLATE in self._value_templates:
                payload = self._value_templates[CONF_HOLD_STATE_TEMPLATE].\
                  async_render_with_possible_json_value(payload)

            self._hold = payload
            self.async_schedule_update_ha_state()

        if self._topic[CONF_HOLD_STATE_TOPIC] is not None:
            topics[CONF_HOLD_STATE_TOPIC] = {
                'topic': self._topic[CONF_HOLD_STATE_TOPIC],
                'msg_callback': handle_hold_mode_received,
                'qos': qos}

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state,
            topics)

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        await subscription.async_unsubscribe_topics(self.hass, self._sub_state)
        await MqttAvailability.async_will_remove_from_hass(self)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._config.get(CONF_NAME)

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
        return self._config.get(CONF_MODE_LIST)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._config.get(CONF_TEMP_STEP)

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
        return self._config.get(CONF_FAN_MODE_LIST)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_OPERATION_MODE) is not None:
            operation_mode = kwargs.get(ATTR_OPERATION_MODE)
            await self.async_set_operation_mode(operation_mode)

        if kwargs.get(ATTR_TEMPERATURE) is not None:
            if self._topic[CONF_TEMPERATURE_STATE_TOPIC] is None:
                # optimistic mode
                self._target_temperature = kwargs.get(ATTR_TEMPERATURE)

            if (self._config.get(CONF_SEND_IF_OFF) or
                    self._current_operation != STATE_OFF):
                mqtt.async_publish(
                    self.hass, self._topic[CONF_TEMPERATURE_COMMAND_TOPIC],
                    kwargs.get(ATTR_TEMPERATURE), self._config.get(CONF_QOS),
                    self._config.get(CONF_RETAIN))

        self.async_schedule_update_ha_state()

    async def async_set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        if (self._config.get(CONF_SEND_IF_OFF) or
                self._current_operation != STATE_OFF):
            mqtt.async_publish(
                self.hass, self._topic[CONF_SWING_MODE_COMMAND_TOPIC],
                swing_mode, self._config.get(CONF_QOS),
                self._config.get(CONF_RETAIN))

        if self._topic[CONF_SWING_MODE_STATE_TOPIC] is None:
            self._current_swing_mode = swing_mode
            self.async_schedule_update_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set new target temperature."""
        if (self._config.get(CONF_SEND_IF_OFF) or
                self._current_operation != STATE_OFF):
            mqtt.async_publish(
                self.hass, self._topic[CONF_FAN_MODE_COMMAND_TOPIC],
                fan_mode, self._config.get(CONF_QOS),
                self._config.get(CONF_RETAIN))

        if self._topic[CONF_FAN_MODE_STATE_TOPIC] is None:
            self._current_fan_mode = fan_mode
            self.async_schedule_update_ha_state()

    async def async_set_operation_mode(self, operation_mode) -> None:
        """Set new operation mode."""
        qos = self._config.get(CONF_QOS)
        retain = self._config.get(CONF_RETAIN)
        if self._topic[CONF_POWER_COMMAND_TOPIC] is not None:
            if (self._current_operation == STATE_OFF and
                    operation_mode != STATE_OFF):
                mqtt.async_publish(
                    self.hass, self._topic[CONF_POWER_COMMAND_TOPIC],
                    self._config.get(CONF_PAYLOAD_ON), qos, retain)
            elif (self._current_operation != STATE_OFF and
                  operation_mode == STATE_OFF):
                mqtt.async_publish(
                    self.hass, self._topic[CONF_POWER_COMMAND_TOPIC],
                    self._config.get(CONF_PAYLOAD_OFF), qos, retain)

        if self._topic[CONF_MODE_COMMAND_TOPIC] is not None:
            mqtt.async_publish(
                self.hass, self._topic[CONF_MODE_COMMAND_TOPIC],
                operation_mode, qos, retain)

        if self._topic[CONF_MODE_STATE_TOPIC] is None:
            self._current_operation = operation_mode
            self.async_schedule_update_ha_state()

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._config.get(CONF_SWING_MODE_LIST)

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        if self._topic[CONF_AWAY_MODE_COMMAND_TOPIC] is not None:
            mqtt.async_publish(self.hass,
                               self._topic[CONF_AWAY_MODE_COMMAND_TOPIC],
                               self._config.get(CONF_PAYLOAD_ON),
                               self._config.get(CONF_QOS),
                               self._config.get(CONF_RETAIN))

        if self._topic[CONF_AWAY_MODE_STATE_TOPIC] is None:
            self._away = True
            self.async_schedule_update_ha_state()

    async def async_turn_away_mode_off(self):
        """Turn away mode off."""
        if self._topic[CONF_AWAY_MODE_COMMAND_TOPIC] is not None:
            mqtt.async_publish(self.hass,
                               self._topic[CONF_AWAY_MODE_COMMAND_TOPIC],
                               self._config.get(CONF_PAYLOAD_OFF),
                               self._config.get(CONF_QOS),
                               self._config.get(CONF_RETAIN))

        if self._topic[CONF_AWAY_MODE_STATE_TOPIC] is None:
            self._away = False
            self.async_schedule_update_ha_state()

    async def async_set_hold_mode(self, hold_mode):
        """Update hold mode on."""
        if self._topic[CONF_HOLD_COMMAND_TOPIC] is not None:
            mqtt.async_publish(self.hass,
                               self._topic[CONF_HOLD_COMMAND_TOPIC],
                               hold_mode, self._config.get(CONF_QOS),
                               self._config.get(CONF_RETAIN))

        if self._topic[CONF_HOLD_STATE_TOPIC] is None:
            self._hold = hold_mode
            self.async_schedule_update_ha_state()

    async def async_turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        if self._topic[CONF_AUX_COMMAND_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._topic[CONF_AUX_COMMAND_TOPIC],
                               self._config.get(CONF_PAYLOAD_ON),
                               self._config.get(CONF_QOS),
                               self._config.get(CONF_RETAIN))

        if self._topic[CONF_AUX_STATE_TOPIC] is None:
            self._aux = True
            self.async_schedule_update_ha_state()

    async def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        if self._topic[CONF_AUX_COMMAND_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._topic[CONF_AUX_COMMAND_TOPIC],
                               self._config.get(CONF_PAYLOAD_OFF),
                               self._config.get(CONF_QOS),
                               self._config.get(CONF_RETAIN))

        if self._topic[CONF_AUX_STATE_TOPIC] is None:
            self._aux = False
            self.async_schedule_update_ha_state()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        support = 0

        if (self._topic[CONF_TEMPERATURE_STATE_TOPIC] is not None) or \
           (self._topic[CONF_TEMPERATURE_COMMAND_TOPIC] is not None):
            support |= SUPPORT_TARGET_TEMPERATURE

        if (self._topic[CONF_MODE_COMMAND_TOPIC] is not None) or \
           (self._topic[CONF_MODE_STATE_TOPIC] is not None):
            support |= SUPPORT_OPERATION_MODE

        if (self._topic[CONF_FAN_MODE_STATE_TOPIC] is not None) or \
           (self._topic[CONF_FAN_MODE_COMMAND_TOPIC] is not None):
            support |= SUPPORT_FAN_MODE

        if (self._topic[CONF_SWING_MODE_STATE_TOPIC] is not None) or \
           (self._topic[CONF_SWING_MODE_COMMAND_TOPIC] is not None):
            support |= SUPPORT_SWING_MODE

        if (self._topic[CONF_AWAY_MODE_STATE_TOPIC] is not None) or \
           (self._topic[CONF_AWAY_MODE_COMMAND_TOPIC] is not None):
            support |= SUPPORT_AWAY_MODE

        if (self._topic[CONF_HOLD_STATE_TOPIC] is not None) or \
           (self._topic[CONF_HOLD_COMMAND_TOPIC] is not None):
            support |= SUPPORT_HOLD_MODE

        if (self._topic[CONF_AUX_STATE_TOPIC] is not None) or \
           (self._topic[CONF_AUX_COMMAND_TOPIC] is not None):
            support |= SUPPORT_AUX_HEAT

        return support

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._config.get(CONF_MIN_TEMP)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._config.get(CONF_MAX_TEMP)
