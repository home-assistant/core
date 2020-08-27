"""Support for MQTT climate devices."""
import logging

import voluptuous as vol

from homeassistant.components import climate, mqtt
from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DEVICE,
    CONF_NAME,
    CONF_TEMPERATURE_UNIT,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_ON,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import (
    ATTR_DISCOVERY_HASH,
    CONF_QOS,
    CONF_RETAIN,
    MQTT_BASE_PLATFORM_SCHEMA,
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    subscription,
)
from .debug_info import log_messages
from .discovery import MQTT_DISCOVERY_NEW, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT HVAC"

CONF_ACTION_TEMPLATE = "action_template"
CONF_ACTION_TOPIC = "action_topic"
CONF_AUX_COMMAND_TOPIC = "aux_command_topic"
CONF_AUX_STATE_TEMPLATE = "aux_state_template"
CONF_AUX_STATE_TOPIC = "aux_state_topic"
CONF_AWAY_MODE_COMMAND_TOPIC = "away_mode_command_topic"
CONF_AWAY_MODE_STATE_TEMPLATE = "away_mode_state_template"
CONF_AWAY_MODE_STATE_TOPIC = "away_mode_state_topic"
CONF_CURRENT_TEMP_TEMPLATE = "current_temperature_template"
CONF_CURRENT_TEMP_TOPIC = "current_temperature_topic"
CONF_FAN_MODE_COMMAND_TOPIC = "fan_mode_command_topic"
CONF_FAN_MODE_LIST = "fan_modes"
CONF_FAN_MODE_STATE_TEMPLATE = "fan_mode_state_template"
CONF_FAN_MODE_STATE_TOPIC = "fan_mode_state_topic"
CONF_HOLD_COMMAND_TOPIC = "hold_command_topic"
CONF_HOLD_STATE_TEMPLATE = "hold_state_template"
CONF_HOLD_STATE_TOPIC = "hold_state_topic"
CONF_HOLD_LIST = "hold_modes"
CONF_MODE_COMMAND_TOPIC = "mode_command_topic"
CONF_MODE_LIST = "modes"
CONF_MODE_STATE_TEMPLATE = "mode_state_template"
CONF_MODE_STATE_TOPIC = "mode_state_topic"
CONF_PAYLOAD_OFF = "payload_off"
CONF_PAYLOAD_ON = "payload_on"
CONF_POWER_COMMAND_TOPIC = "power_command_topic"
CONF_POWER_STATE_TEMPLATE = "power_state_template"
CONF_POWER_STATE_TOPIC = "power_state_topic"
CONF_PRECISION = "precision"
CONF_SEND_IF_OFF = "send_if_off"
CONF_SWING_MODE_COMMAND_TOPIC = "swing_mode_command_topic"
CONF_SWING_MODE_LIST = "swing_modes"
CONF_SWING_MODE_STATE_TEMPLATE = "swing_mode_state_template"
CONF_SWING_MODE_STATE_TOPIC = "swing_mode_state_topic"
CONF_TEMP_COMMAND_TOPIC = "temperature_command_topic"
CONF_TEMP_HIGH_COMMAND_TOPIC = "temperature_high_command_topic"
CONF_TEMP_HIGH_STATE_TEMPLATE = "temperature_high_state_template"
CONF_TEMP_HIGH_STATE_TOPIC = "temperature_high_state_topic"
CONF_TEMP_LOW_COMMAND_TOPIC = "temperature_low_command_topic"
CONF_TEMP_LOW_STATE_TEMPLATE = "temperature_low_state_template"
CONF_TEMP_LOW_STATE_TOPIC = "temperature_low_state_topic"
CONF_TEMP_STATE_TEMPLATE = "temperature_state_template"
CONF_TEMP_STATE_TOPIC = "temperature_state_topic"
CONF_TEMP_INITIAL = "initial"
CONF_TEMP_MAX = "max_temp"
CONF_TEMP_MIN = "min_temp"
CONF_TEMP_STEP = "temp_step"

TEMPLATE_KEYS = (
    CONF_AUX_STATE_TEMPLATE,
    CONF_AWAY_MODE_STATE_TEMPLATE,
    CONF_CURRENT_TEMP_TEMPLATE,
    CONF_FAN_MODE_STATE_TEMPLATE,
    CONF_HOLD_STATE_TEMPLATE,
    CONF_MODE_STATE_TEMPLATE,
    CONF_POWER_STATE_TEMPLATE,
    CONF_ACTION_TEMPLATE,
    CONF_SWING_MODE_STATE_TEMPLATE,
    CONF_TEMP_HIGH_STATE_TEMPLATE,
    CONF_TEMP_LOW_STATE_TEMPLATE,
    CONF_TEMP_STATE_TEMPLATE,
)

TOPIC_KEYS = (
    CONF_AUX_COMMAND_TOPIC,
    CONF_AUX_STATE_TOPIC,
    CONF_AWAY_MODE_COMMAND_TOPIC,
    CONF_AWAY_MODE_STATE_TOPIC,
    CONF_CURRENT_TEMP_TOPIC,
    CONF_FAN_MODE_COMMAND_TOPIC,
    CONF_FAN_MODE_STATE_TOPIC,
    CONF_HOLD_COMMAND_TOPIC,
    CONF_HOLD_STATE_TOPIC,
    CONF_MODE_COMMAND_TOPIC,
    CONF_MODE_STATE_TOPIC,
    CONF_POWER_COMMAND_TOPIC,
    CONF_POWER_STATE_TOPIC,
    CONF_ACTION_TOPIC,
    CONF_SWING_MODE_COMMAND_TOPIC,
    CONF_SWING_MODE_STATE_TOPIC,
    CONF_TEMP_COMMAND_TOPIC,
    CONF_TEMP_HIGH_COMMAND_TOPIC,
    CONF_TEMP_HIGH_STATE_TOPIC,
    CONF_TEMP_LOW_COMMAND_TOPIC,
    CONF_TEMP_LOW_STATE_TOPIC,
    CONF_TEMP_STATE_TOPIC,
)

SCHEMA_BASE = CLIMATE_PLATFORM_SCHEMA.extend(MQTT_BASE_PLATFORM_SCHEMA.schema)
PLATFORM_SCHEMA = (
    SCHEMA_BASE.extend(
        {
            vol.Optional(CONF_AUX_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_AUX_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_AUX_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_AWAY_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_AWAY_MODE_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_AWAY_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_CURRENT_TEMP_TEMPLATE): cv.template,
            vol.Optional(CONF_CURRENT_TEMP_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            vol.Optional(CONF_FAN_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(
                CONF_FAN_MODE_LIST,
                default=[FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
            ): cv.ensure_list,
            vol.Optional(CONF_FAN_MODE_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_FAN_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_HOLD_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_HOLD_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_HOLD_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_HOLD_LIST, default=list): cv.ensure_list,
            vol.Optional(CONF_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(
                CONF_MODE_LIST,
                default=[
                    HVAC_MODE_AUTO,
                    HVAC_MODE_OFF,
                    HVAC_MODE_COOL,
                    HVAC_MODE_HEAT,
                    HVAC_MODE_DRY,
                    HVAC_MODE_FAN_ONLY,
                ],
            ): cv.ensure_list,
            vol.Optional(CONF_MODE_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_PAYLOAD_ON, default="ON"): cv.string,
            vol.Optional(CONF_PAYLOAD_OFF, default="OFF"): cv.string,
            vol.Optional(CONF_POWER_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_POWER_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_POWER_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_PRECISION): vol.In(
                [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
            ),
            vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
            vol.Optional(CONF_SEND_IF_OFF, default=True): cv.boolean,
            vol.Optional(CONF_ACTION_TEMPLATE): cv.template,
            vol.Optional(CONF_ACTION_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_SWING_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(
                CONF_SWING_MODE_LIST, default=[STATE_ON, HVAC_MODE_OFF]
            ): cv.ensure_list,
            vol.Optional(CONF_SWING_MODE_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_SWING_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_TEMP_INITIAL, default=21): cv.positive_int,
            vol.Optional(CONF_TEMP_MIN, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
            vol.Optional(CONF_TEMP_MAX, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
            vol.Optional(CONF_TEMP_STEP, default=1.0): vol.Coerce(float),
            vol.Optional(CONF_TEMP_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_TEMP_HIGH_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_TEMP_HIGH_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_TEMP_HIGH_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_TEMP_LOW_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_TEMP_LOW_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_TEMP_LOW_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_TEMP_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_TEMP_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        }
    )
    .extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(mqtt.MQTT_JSON_ATTRS_SCHEMA.schema)
)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT climate device through configuration.yaml."""
    await _async_setup_entity(hass, config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT climate device dynamically through MQTT discovery."""

    async def async_discover(discovery_payload):
        """Discover and add a MQTT climate device."""
        discovery_data = discovery_payload.discovery_data
        try:
            config = PLATFORM_SCHEMA(discovery_payload)
            await _async_setup_entity(
                hass, config, async_add_entities, config_entry, discovery_data
            )
        except Exception:
            clear_discovery_hash(hass, discovery_data[ATTR_DISCOVERY_HASH])
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(climate.DOMAIN, "mqtt"), async_discover
    )


async def _async_setup_entity(
    hass, config, async_add_entities, config_entry=None, discovery_data=None
):
    """Set up the MQTT climate devices."""
    async_add_entities([MqttClimate(hass, config, config_entry, discovery_data)])


class MqttClimate(
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    ClimateEntity,
):
    """Representation of an MQTT climate device."""

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the climate device."""
        self._config = config
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._sub_state = None

        self.hass = hass
        self._action = None
        self._aux = False
        self._away = False
        self._current_fan_mode = None
        self._current_operation = None
        self._current_swing_mode = None
        self._current_temp = None
        self._hold = None
        self._target_temp = None
        self._target_temp_high = None
        self._target_temp_low = None
        self._topic = None
        self._value_templates = None

        self._setup_from_config(config)

        device_config = config.get(CONF_DEVICE)

        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_data, self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config, config_entry)

    async def async_added_to_hass(self):
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA(discovery_payload)
        self._config = config
        self._setup_from_config(config)
        await self.attributes_discovery_update(config)
        await self.availability_discovery_update(config)
        await self.device_info_discovery_update(config)
        await self._subscribe_topics()
        self.async_write_ha_state()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._topic = {key: config.get(key) for key in TOPIC_KEYS}

        # set to None in non-optimistic mode
        self._target_temp = (
            self._current_fan_mode
        ) = self._current_operation = self._current_swing_mode = None
        self._target_temp_low = None
        self._target_temp_high = None

        if self._topic[CONF_TEMP_STATE_TOPIC] is None:
            self._target_temp = config[CONF_TEMP_INITIAL]
        if self._topic[CONF_TEMP_LOW_STATE_TOPIC] is None:
            self._target_temp_low = config[CONF_TEMP_INITIAL]
        if self._topic[CONF_TEMP_HIGH_STATE_TOPIC] is None:
            self._target_temp_high = config[CONF_TEMP_INITIAL]

        if self._topic[CONF_FAN_MODE_STATE_TOPIC] is None:
            self._current_fan_mode = FAN_LOW
        if self._topic[CONF_SWING_MODE_STATE_TOPIC] is None:
            self._current_swing_mode = HVAC_MODE_OFF
        if self._topic[CONF_MODE_STATE_TOPIC] is None:
            self._current_operation = HVAC_MODE_OFF
        self._action = None
        self._away = False
        self._hold = None
        self._aux = False

        value_templates = {}
        for key in TEMPLATE_KEYS:
            value_templates[key] = lambda value: value
        if CONF_VALUE_TEMPLATE in config:
            value_template = config.get(CONF_VALUE_TEMPLATE)
            value_template.hass = self.hass
            value_templates = {
                key: value_template.async_render_with_possible_json_value
                for key in TEMPLATE_KEYS
            }
        for key in TEMPLATE_KEYS & config.keys():
            tpl = config[key]
            value_templates[key] = tpl.async_render_with_possible_json_value
            tpl.hass = self.hass
        self._value_templates = value_templates

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}
        qos = self._config[CONF_QOS]

        def add_subscription(topics, topic, msg_callback):
            if self._topic[topic] is not None:
                topics[topic] = {
                    "topic": self._topic[topic],
                    "msg_callback": msg_callback,
                    "qos": qos,
                }

        def render_template(msg, template_name):
            template = self._value_templates[template_name]
            return template(msg.payload)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_action_received(msg):
            """Handle receiving action via MQTT."""
            payload = render_template(msg, CONF_ACTION_TEMPLATE)

            self._action = payload
            self.async_write_ha_state()

        add_subscription(topics, CONF_ACTION_TOPIC, handle_action_received)

        @callback
        def handle_temperature_received(msg, template_name, attr):
            """Handle temperature coming via MQTT."""
            payload = render_template(msg, template_name)

            try:
                setattr(self, attr, float(payload))
                self.async_write_ha_state()
            except ValueError:
                _LOGGER.error("Could not parse temperature from %s", payload)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_current_temperature_received(msg):
            """Handle current temperature coming via MQTT."""
            handle_temperature_received(
                msg, CONF_CURRENT_TEMP_TEMPLATE, "_current_temp"
            )

        add_subscription(
            topics, CONF_CURRENT_TEMP_TOPIC, handle_current_temperature_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_target_temperature_received(msg):
            """Handle target temperature coming via MQTT."""
            handle_temperature_received(msg, CONF_TEMP_STATE_TEMPLATE, "_target_temp")

        add_subscription(
            topics, CONF_TEMP_STATE_TOPIC, handle_target_temperature_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_temperature_low_received(msg):
            """Handle target temperature low coming via MQTT."""
            handle_temperature_received(
                msg, CONF_TEMP_LOW_STATE_TEMPLATE, "_target_temp_low"
            )

        add_subscription(
            topics, CONF_TEMP_LOW_STATE_TOPIC, handle_temperature_low_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_temperature_high_received(msg):
            """Handle target temperature high coming via MQTT."""
            handle_temperature_received(
                msg, CONF_TEMP_HIGH_STATE_TEMPLATE, "_target_temp_high"
            )

        add_subscription(
            topics, CONF_TEMP_HIGH_STATE_TOPIC, handle_temperature_high_received
        )

        @callback
        def handle_mode_received(msg, template_name, attr, mode_list):
            """Handle receiving listed mode via MQTT."""
            payload = render_template(msg, template_name)

            if payload not in self._config[mode_list]:
                _LOGGER.error("Invalid %s mode: %s", mode_list, payload)
            else:
                setattr(self, attr, payload)
                self.async_write_ha_state()

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_current_mode_received(msg):
            """Handle receiving mode via MQTT."""
            handle_mode_received(
                msg, CONF_MODE_STATE_TEMPLATE, "_current_operation", CONF_MODE_LIST
            )

        add_subscription(topics, CONF_MODE_STATE_TOPIC, handle_current_mode_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_fan_mode_received(msg):
            """Handle receiving fan mode via MQTT."""
            handle_mode_received(
                msg,
                CONF_FAN_MODE_STATE_TEMPLATE,
                "_current_fan_mode",
                CONF_FAN_MODE_LIST,
            )

        add_subscription(topics, CONF_FAN_MODE_STATE_TOPIC, handle_fan_mode_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_swing_mode_received(msg):
            """Handle receiving swing mode via MQTT."""
            handle_mode_received(
                msg,
                CONF_SWING_MODE_STATE_TEMPLATE,
                "_current_swing_mode",
                CONF_SWING_MODE_LIST,
            )

        add_subscription(
            topics, CONF_SWING_MODE_STATE_TOPIC, handle_swing_mode_received
        )

        @callback
        def handle_onoff_mode_received(msg, template_name, attr):
            """Handle receiving on/off mode via MQTT."""
            payload = render_template(msg, template_name)
            payload_on = self._config[CONF_PAYLOAD_ON]
            payload_off = self._config[CONF_PAYLOAD_OFF]

            if payload == "True":
                payload = payload_on
            elif payload == "False":
                payload = payload_off

            if payload == payload_on:
                setattr(self, attr, True)
            elif payload == payload_off:
                setattr(self, attr, False)
            else:
                _LOGGER.error("Invalid %s mode: %s", attr, payload)

            self.async_write_ha_state()

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_away_mode_received(msg):
            """Handle receiving away mode via MQTT."""
            handle_onoff_mode_received(msg, CONF_AWAY_MODE_STATE_TEMPLATE, "_away")

        add_subscription(topics, CONF_AWAY_MODE_STATE_TOPIC, handle_away_mode_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_aux_mode_received(msg):
            """Handle receiving aux mode via MQTT."""
            handle_onoff_mode_received(msg, CONF_AUX_STATE_TEMPLATE, "_aux")

        add_subscription(topics, CONF_AUX_STATE_TOPIC, handle_aux_mode_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_hold_mode_received(msg):
            """Handle receiving hold mode via MQTT."""
            payload = render_template(msg, CONF_HOLD_STATE_TEMPLATE)

            if payload == "off":
                payload = None

            self._hold = payload
            self.async_write_ha_state()

        add_subscription(topics, CONF_HOLD_STATE_TOPIC, handle_hold_mode_received)

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        await MqttAttributes.async_will_remove_from_hass(self)
        await MqttAvailability.async_will_remove_from_hass(self)
        await MqttDiscoveryUpdate.async_will_remove_from_hass(self)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._config[CONF_NAME]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._config.get(CONF_TEMPERATURE_UNIT):
            return self._config.get(CONF_TEMPERATURE_UNIT)
        return self.hass.config.units.temperature_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def target_temperature_low(self):
        """Return the low target temperature we try to reach."""
        return self._target_temp_low

    @property
    def target_temperature_high(self):
        """Return the high target temperature we try to reach."""
        return self._target_temp_high

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported."""
        return self._action

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._config[CONF_MODE_LIST]

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._config[CONF_TEMP_STEP]

    @property
    def preset_mode(self):
        """Return preset mode."""
        if self._hold:
            return self._hold
        if self._away:
            return PRESET_AWAY
        return None

    @property
    def preset_modes(self):
        """Return preset modes."""
        presets = []

        if (self._topic[CONF_AWAY_MODE_STATE_TOPIC] is not None) or (
            self._topic[CONF_AWAY_MODE_COMMAND_TOPIC] is not None
        ):
            presets.append(PRESET_AWAY)

        presets.extend(self._config[CONF_HOLD_LIST])

        if presets:
            presets.insert(0, PRESET_NONE)

        return presets

    @property
    def is_aux_heat(self):
        """Return true if away mode is on."""
        return self._aux

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._config[CONF_FAN_MODE_LIST]

    def _publish(self, topic, payload):
        if self._topic[topic] is not None:
            mqtt.async_publish(
                self.hass,
                self._topic[topic],
                payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
            )

    def _set_temperature(self, temp, cmnd_topic, state_topic, attr):
        if temp is not None:
            if self._topic[state_topic] is None:
                # optimistic mode
                setattr(self, attr, temp)

            if (
                self._config[CONF_SEND_IF_OFF]
                or self._current_operation != HVAC_MODE_OFF
            ):
                self._publish(cmnd_topic, temp)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_HVAC_MODE) is not None:
            operation_mode = kwargs.get(ATTR_HVAC_MODE)
            await self.async_set_hvac_mode(operation_mode)

        self._set_temperature(
            kwargs.get(ATTR_TEMPERATURE),
            CONF_TEMP_COMMAND_TOPIC,
            CONF_TEMP_STATE_TOPIC,
            "_target_temp",
        )

        self._set_temperature(
            kwargs.get(ATTR_TARGET_TEMP_LOW),
            CONF_TEMP_LOW_COMMAND_TOPIC,
            CONF_TEMP_LOW_STATE_TOPIC,
            "_target_temp_low",
        )

        self._set_temperature(
            kwargs.get(ATTR_TARGET_TEMP_HIGH),
            CONF_TEMP_HIGH_COMMAND_TOPIC,
            CONF_TEMP_HIGH_STATE_TOPIC,
            "_target_temp_high",
        )

        # Always optimistic?
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        if self._config[CONF_SEND_IF_OFF] or self._current_operation != HVAC_MODE_OFF:
            self._publish(CONF_SWING_MODE_COMMAND_TOPIC, swing_mode)

        if self._topic[CONF_SWING_MODE_STATE_TOPIC] is None:
            self._current_swing_mode = swing_mode
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set new target temperature."""
        if self._config[CONF_SEND_IF_OFF] or self._current_operation != HVAC_MODE_OFF:
            self._publish(CONF_FAN_MODE_COMMAND_TOPIC, fan_mode)

        if self._topic[CONF_FAN_MODE_STATE_TOPIC] is None:
            self._current_fan_mode = fan_mode
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode) -> None:
        """Set new operation mode."""
        if self._current_operation == HVAC_MODE_OFF and hvac_mode != HVAC_MODE_OFF:
            self._publish(CONF_POWER_COMMAND_TOPIC, self._config[CONF_PAYLOAD_ON])
        elif self._current_operation != HVAC_MODE_OFF and hvac_mode == HVAC_MODE_OFF:
            self._publish(CONF_POWER_COMMAND_TOPIC, self._config[CONF_PAYLOAD_OFF])

        self._publish(CONF_MODE_COMMAND_TOPIC, hvac_mode)

        if self._topic[CONF_MODE_STATE_TOPIC] is None:
            self._current_operation = hvac_mode
            self.async_write_ha_state()

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return self._config[CONF_SWING_MODE_LIST]

    async def async_set_preset_mode(self, preset_mode):
        """Set a preset mode."""
        if preset_mode == self.preset_mode:
            return

        # Track if we should optimistic update the state
        optimistic_update = False

        if self._away:
            optimistic_update = optimistic_update or self._set_away_mode(False)
        elif preset_mode == PRESET_AWAY:
            if self._hold:
                self._set_hold_mode(None)
            optimistic_update = optimistic_update or self._set_away_mode(True)
        else:
            hold_mode = preset_mode
            if preset_mode == PRESET_NONE:
                hold_mode = None
            optimistic_update = optimistic_update or self._set_hold_mode(hold_mode)

        if optimistic_update:
            self.async_write_ha_state()

    def _set_away_mode(self, state):
        """Set away mode.

        Returns if we should optimistically write the state.
        """
        self._publish(
            CONF_AWAY_MODE_COMMAND_TOPIC,
            self._config[CONF_PAYLOAD_ON] if state else self._config[CONF_PAYLOAD_OFF],
        )

        if self._topic[CONF_AWAY_MODE_STATE_TOPIC] is not None:
            return False

        self._away = state
        return True

    def _set_hold_mode(self, hold_mode):
        """Set hold mode.

        Returns if we should optimistically write the state.
        """
        self._publish(CONF_HOLD_COMMAND_TOPIC, hold_mode or "off")

        if self._topic[CONF_HOLD_STATE_TOPIC] is not None:
            return False

        self._hold = hold_mode
        return True

    def _set_aux_heat(self, state):
        self._publish(
            CONF_AUX_COMMAND_TOPIC,
            self._config[CONF_PAYLOAD_ON] if state else self._config[CONF_PAYLOAD_OFF],
        )

        if self._topic[CONF_AUX_STATE_TOPIC] is None:
            self._aux = state
            self.async_write_ha_state()

    async def async_turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self._set_aux_heat(True)

    async def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self._set_aux_heat(False)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        support = 0

        if (self._topic[CONF_TEMP_STATE_TOPIC] is not None) or (
            self._topic[CONF_TEMP_COMMAND_TOPIC] is not None
        ):
            support |= SUPPORT_TARGET_TEMPERATURE

        if (self._topic[CONF_TEMP_LOW_STATE_TOPIC] is not None) or (
            self._topic[CONF_TEMP_LOW_COMMAND_TOPIC] is not None
        ):
            support |= SUPPORT_TARGET_TEMPERATURE_RANGE

        if (self._topic[CONF_TEMP_HIGH_STATE_TOPIC] is not None) or (
            self._topic[CONF_TEMP_HIGH_COMMAND_TOPIC] is not None
        ):
            support |= SUPPORT_TARGET_TEMPERATURE_RANGE

        if (self._topic[CONF_FAN_MODE_STATE_TOPIC] is not None) or (
            self._topic[CONF_FAN_MODE_COMMAND_TOPIC] is not None
        ):
            support |= SUPPORT_FAN_MODE

        if (self._topic[CONF_SWING_MODE_STATE_TOPIC] is not None) or (
            self._topic[CONF_SWING_MODE_COMMAND_TOPIC] is not None
        ):
            support |= SUPPORT_SWING_MODE

        if (
            (self._topic[CONF_AWAY_MODE_STATE_TOPIC] is not None)
            or (self._topic[CONF_AWAY_MODE_COMMAND_TOPIC] is not None)
            or (self._topic[CONF_HOLD_STATE_TOPIC] is not None)
            or (self._topic[CONF_HOLD_COMMAND_TOPIC] is not None)
        ):
            support |= SUPPORT_PRESET_MODE

        if (self._topic[CONF_AUX_STATE_TOPIC] is not None) or (
            self._topic[CONF_AUX_COMMAND_TOPIC] is not None
        ):
            support |= SUPPORT_AUX_HEAT

        return support

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._config[CONF_TEMP_MIN]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._config[CONF_TEMP_MAX]

    @property
    def precision(self):
        """Return the precision of the system."""
        if self._config.get(CONF_PRECISION) is not None:
            return self._config.get(CONF_PRECISION)
        return super().precision
