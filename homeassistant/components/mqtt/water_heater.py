"""Support for MQTT water heater devices."""
from __future__ import annotations

from collections.abc import Callable
import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import water_heater
from homeassistant.components.water_heater import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_TEMPERATURE_UNIT,
    CONF_VALUE_TEMPLATE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import DEFAULT_RETAIN, MQTT_BASE_SCHEMA
from .const import (
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    DEFAULT_OPTIMISTIC,
    PAYLOAD_NONE,
)
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import get_mqtt_data, valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Water Heater"

CONF_AWAY_MODE_COMMAND_TOPIC = "away_mode_command_topic"
CONF_AWAY_MODE_STATE_TEMPLATE = "away_mode_state_template"
CONF_AWAY_MODE_STATE_TOPIC = "away_mode_state_topic"
CONF_CURRENT_TEMP_TEMPLATE = "current_temperature_template"
CONF_CURRENT_TEMP_TOPIC = "current_temperature_topic"
CONF_OPERATION_MODE_COMMAND_TEMPLATE = "operation_mode_command_template"
CONF_OPERATION_MODE_COMMAND_TOPIC = "operation_mode_command_topic"
CONF_OPERATION_MODE_STATE_TEMPLATE = "operation_mode_state_template"
CONF_OPERATION_MODE_STATE_TOPIC = "operation_mode_state_topic"
CONF_OPERATION_MODE_LIST = "operation_modes"
CONF_POWER_COMMAND_TOPIC = "power_command_topic"
CONF_POWER_STATE_TEMPLATE = "power_state_template"
CONF_POWER_STATE_TOPIC = "power_state_topic"
CONF_PRECISION = "precision"
CONF_TEMP_COMMAND_TEMPLATE = "temperature_command_template"
CONF_TEMP_COMMAND_TOPIC = "temperature_command_topic"
CONF_TEMP_HIGH_COMMAND_TEMPLATE = "temperature_high_command_template"
CONF_TEMP_HIGH_COMMAND_TOPIC = "temperature_high_command_topic"
CONF_TEMP_HIGH_STATE_TEMPLATE = "temperature_high_state_template"
CONF_TEMP_HIGH_STATE_TOPIC = "temperature_high_state_topic"
CONF_TEMP_LOW_COMMAND_TEMPLATE = "temperature_low_command_template"
CONF_TEMP_LOW_COMMAND_TOPIC = "temperature_low_command_topic"
CONF_TEMP_LOW_STATE_TEMPLATE = "temperature_low_state_template"
CONF_TEMP_LOW_STATE_TOPIC = "temperature_low_state_topic"
CONF_TEMP_STATE_TEMPLATE = "temperature_state_template"
CONF_TEMP_STATE_TOPIC = "temperature_state_topic"
CONF_TEMP_INITIAL = "initial"
CONF_TEMP_MAX = "max_temp"
CONF_TEMP_MIN = "min_temp"
CONF_TEMP_STEP = "temp_step"

MQTT_WATER_HEATER_ATTRIBUTES_BLOCKED = frozenset(
    {
        water_heater.ATTR_CURRENT_TEMPERATURE,
        water_heater.ATTR_MAX_TEMP,
        water_heater.ATTR_MIN_TEMP,
        water_heater.ATTR_TARGET_TEMP_HIGH,
        water_heater.ATTR_TARGET_TEMP_LOW,
        water_heater.ATTR_TEMPERATURE,
        water_heater.ATTR_OPERATION_LIST,
        water_heater.ATTR_OPERATION_MODE,
    }
)

VALUE_TEMPLATE_KEYS = (
    CONF_AWAY_MODE_STATE_TEMPLATE,
    CONF_CURRENT_TEMP_TEMPLATE,
    CONF_OPERATION_MODE_STATE_TEMPLATE,
    CONF_POWER_STATE_TEMPLATE,
    CONF_TEMP_HIGH_STATE_TEMPLATE,
    CONF_TEMP_LOW_STATE_TEMPLATE,
    CONF_TEMP_STATE_TEMPLATE,
)

COMMAND_TEMPLATE_KEYS = {
    CONF_OPERATION_MODE_COMMAND_TEMPLATE,
    CONF_TEMP_COMMAND_TEMPLATE,
    CONF_TEMP_HIGH_COMMAND_TEMPLATE,
    CONF_TEMP_LOW_COMMAND_TEMPLATE,
}


TOPIC_KEYS = (
    CONF_AWAY_MODE_COMMAND_TOPIC,
    CONF_AWAY_MODE_STATE_TOPIC,
    CONF_CURRENT_TEMP_TOPIC,
    CONF_OPERATION_MODE_COMMAND_TOPIC,
    CONF_OPERATION_MODE_STATE_TOPIC,
    CONF_POWER_COMMAND_TOPIC,
    CONF_POWER_STATE_TOPIC,
    CONF_TEMP_COMMAND_TOPIC,
    CONF_TEMP_HIGH_COMMAND_TOPIC,
    CONF_TEMP_HIGH_STATE_TOPIC,
    CONF_TEMP_LOW_COMMAND_TOPIC,
    CONF_TEMP_LOW_STATE_TOPIC,
    CONF_TEMP_STATE_TOPIC,
)


_PLATFORM_SCHEMA_BASE = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_AWAY_MODE_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_AWAY_MODE_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_AWAY_MODE_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_CURRENT_TEMP_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_TEMP_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_OPERATION_MODE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_OPERATION_MODE_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(
            CONF_OPERATION_MODE_LIST,
            default=[
                STATE_ECO,
                STATE_ELECTRIC,
                STATE_GAS,
                STATE_HEAT_PUMP,
                STATE_HIGH_DEMAND,
                STATE_PERFORMANCE,
                STATE_OFF,
            ],
        ): cv.ensure_list,
        vol.Optional(CONF_OPERATION_MODE_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_OPERATION_MODE_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_ON, default="ON"): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default="OFF"): cv.string,
        vol.Optional(CONF_POWER_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_POWER_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_POWER_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_TEMP_MIN, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TEMP_MAX, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TEMP_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_TEMP_HIGH_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_HIGH_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_TEMP_HIGH_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_TEMP_HIGH_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_LOW_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_LOW_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_TEMP_LOW_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_LOW_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_TEMP_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE,
)

_DISCOVERY_SCHEMA_BASE = _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA)

DISCOVERY_SCHEMA = vol.All(
    _DISCOVERY_SCHEMA_BASE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT water heater device through YAML and through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, water_heater.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT water heater devices."""
    async_add_entities([MqttWaterHeater(hass, config, config_entry, discovery_data)])


class MqttWaterHeater(MqttEntity, WaterHeaterEntity):
    """Representation of an MQTT water heater device."""

    _entity_id_format = water_heater.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_WATER_HEATER_ATTRIBUTES_BLOCKED

    _command_templates: dict[str, Callable[[PublishPayloadType], PublishPayloadType]]
    _value_templates: dict[str, Callable[[ReceivePayloadType], ReceivePayloadType]]
    _optimistic: bool
    _topic: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the water heater device."""
        self._attr_current_operation = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_min_temp = config[CONF_TEMP_MIN]
        self._attr_max_temp = config[CONF_TEMP_MAX]
        self._attr_precision = config.get(CONF_PRECISION, super().precision)
        self._attr_operation_modes = config[CONF_OPERATION_MODE_LIST]
        self._attr_temperature_unit = config.get(
            CONF_TEMPERATURE_UNIT, self.hass.config.units.temperature_unit
        )

        self._topic = {key: config.get(key) for key in TOPIC_KEYS}

        self._optimistic = config[CONF_OPTIMISTIC]

        if self._topic[CONF_TEMP_STATE_TOPIC] is None or self._optimistic:
            self._attr_target_temperature = config[CONF_TEMP_INITIAL]
        if self._topic[CONF_TEMP_LOW_STATE_TOPIC] is None or self._optimistic:
            self._attr_target_temperature_low = config[CONF_TEMP_INITIAL]
        if self._topic[CONF_TEMP_HIGH_STATE_TOPIC] is None or self._optimistic:
            self._attr_target_temperature_high = config[CONF_TEMP_INITIAL]
        if self._topic[CONF_OPERATION_MODE_STATE_TOPIC] is None or self._optimistic:
            self._attr_current_operation = STATE_OFF

        value_templates: dict[str, Template | None] = {}
        for key in VALUE_TEMPLATE_KEYS:
            value_templates[key] = None
        if CONF_VALUE_TEMPLATE in config:
            value_templates = {
                key: config.get(CONF_VALUE_TEMPLATE) for key in VALUE_TEMPLATE_KEYS
            }
        for key in VALUE_TEMPLATE_KEYS & config.keys():
            value_templates[key] = config[key]
        self._value_templates = {
            key: MqttValueTemplate(
                template,
                entity=self,
            ).async_render_with_possible_json_value
            for key, template in value_templates.items()
        }

        self._command_templates = {}
        for key in COMMAND_TEMPLATE_KEYS:
            self._command_templates[key] = MqttCommandTemplate(
                config.get(key), entity=self
            ).async_render

        support = WaterHeaterEntityFeature(0)
        if (self._topic[CONF_TEMP_STATE_TOPIC] is not None) or (
            self._topic[CONF_TEMP_COMMAND_TOPIC] is not None
        ):
            support |= WaterHeaterEntityFeature.TARGET_TEMPERATURE

        if (self._topic[CONF_OPERATION_MODE_STATE_TOPIC] is not None) or (
            self._topic[CONF_OPERATION_MODE_COMMAND_TOPIC] is not None
        ):
            support |= WaterHeaterEntityFeature.OPERATION_MODE

        self._attr_supported_features = support

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        topics: dict[str, dict[str, Any]] = {}
        qos: int = self._config[CONF_QOS]

        def add_subscription(
            topics: dict[str, dict[str, Any]],
            topic: str,
            msg_callback: Callable[[ReceiveMessage], None],
        ) -> None:
            if self._topic[topic] is not None:
                topics[topic] = {
                    "topic": self._topic[topic],
                    "msg_callback": msg_callback,
                    "qos": qos,
                    "encoding": self._config[CONF_ENCODING] or None,
                }

        def render_template(
            msg: ReceiveMessage, template_name: str
        ) -> ReceivePayloadType:
            template = self._value_templates[template_name]
            return template(msg.payload)

        @callback
        def handle_temperature_received(
            msg: ReceiveMessage, template_name: str, attr: str
        ) -> None:
            """Handle temperature coming via MQTT."""
            payload = render_template(msg, template_name)

            if not payload:
                _LOGGER.debug(
                    "Invalid empty payload for attribute %s, ignoring update",
                    attr,
                )
                return
            if payload == PAYLOAD_NONE:
                setattr(self, attr, None)
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)
                return

            try:
                setattr(self, attr, float(payload))
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)
            except ValueError:
                _LOGGER.error("Could not parse temperature from %s", payload)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_current_temperature_received(msg: ReceiveMessage) -> None:
            """Handle current temperature coming via MQTT."""
            handle_temperature_received(
                msg, CONF_CURRENT_TEMP_TEMPLATE, "_attr_current_temperature"
            )

        add_subscription(
            topics, CONF_CURRENT_TEMP_TOPIC, handle_current_temperature_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_target_temperature_received(msg: ReceiveMessage) -> None:
            """Handle target temperature coming via MQTT."""
            handle_temperature_received(
                msg, CONF_TEMP_STATE_TEMPLATE, "_attr_target_temperature"
            )

        add_subscription(
            topics, CONF_TEMP_STATE_TOPIC, handle_target_temperature_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_temperature_low_received(msg: ReceiveMessage) -> None:
            """Handle target temperature low coming via MQTT."""
            handle_temperature_received(
                msg, CONF_TEMP_LOW_STATE_TEMPLATE, "_attr_target_temperature_low"
            )

        add_subscription(
            topics, CONF_TEMP_LOW_STATE_TOPIC, handle_temperature_low_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_temperature_high_received(msg: ReceiveMessage) -> None:
            """Handle target temperature high coming via MQTT."""
            handle_temperature_received(
                msg, CONF_TEMP_HIGH_STATE_TEMPLATE, "_attr_target_temperature_high"
            )

        add_subscription(
            topics, CONF_TEMP_HIGH_STATE_TOPIC, handle_temperature_high_received
        )

        @callback
        def handle_mode_received(
            msg: ReceiveMessage, template_name: str, attr: str, mode_list: str
        ) -> None:
            """Handle receiving listed mode via MQTT."""
            payload = render_template(msg, template_name)

            if payload not in self._config[mode_list]:
                _LOGGER.error("Invalid %s mode: %s", mode_list, payload)
            else:
                setattr(self, attr, payload)
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_current_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving mode via MQTT."""
            handle_mode_received(
                msg,
                CONF_OPERATION_MODE_STATE_TEMPLATE,
                "_attr_current_operation",
                CONF_OPERATION_MODE_LIST,
            )

        add_subscription(
            topics, CONF_OPERATION_MODE_STATE_TOPIC, handle_current_mode_received
        )

        @callback
        def handle_onoff_mode_received(
            msg: ReceiveMessage, template_name: str, attr: str
        ) -> None:
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

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_away_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving away mode via MQTT."""
            handle_onoff_mode_received(
                msg, CONF_AWAY_MODE_STATE_TEMPLATE, "_attr_away_mode"
            )

        add_subscription(topics, CONF_AWAY_MODE_STATE_TOPIC, handle_away_mode_received)

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    async def _publish(self, topic: str, payload: PublishPayloadType) -> None:
        if self._topic[topic] is not None:
            await self.async_publish(
                self._topic[topic],
                payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
                self._config[CONF_ENCODING],
            )

    async def _set_temperature(
        self,
        temp: float | None,
        cmnd_topic: str,
        cmnd_template: str,
        state_topic: str,
        attr: str,
    ) -> bool:
        if temp is None:
            return False
        changed = False
        if self._optimistic or self._topic[state_topic] is None:
            # optimistic mode
            changed = True
            setattr(self, attr, temp)

        payload = self._command_templates[cmnd_template](temp)
        await self._publish(cmnd_topic, payload)
        return changed

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        changed = await self._set_temperature(
            kwargs.get(ATTR_TEMPERATURE),
            CONF_TEMP_COMMAND_TOPIC,
            CONF_TEMP_COMMAND_TEMPLATE,
            CONF_TEMP_STATE_TOPIC,
            "_attr_target_temperature",
        )

        changed |= await self._set_temperature(
            kwargs.get(ATTR_TARGET_TEMP_LOW),
            CONF_TEMP_LOW_COMMAND_TOPIC,
            CONF_TEMP_LOW_COMMAND_TEMPLATE,
            CONF_TEMP_LOW_STATE_TOPIC,
            "_attr_target_temperature_low",
        )

        changed |= await self._set_temperature(
            kwargs.get(ATTR_TARGET_TEMP_HIGH),
            CONF_TEMP_HIGH_COMMAND_TOPIC,
            CONF_TEMP_HIGH_COMMAND_TEMPLATE,
            CONF_TEMP_HIGH_STATE_TOPIC,
            "_attr_target_temperature_high",
        )

        if not changed:
            return
        self.async_write_ha_state()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        payload = self._command_templates[CONF_OPERATION_MODE_COMMAND_TEMPLATE](
            operation_mode
        )
        await self._publish(CONF_OPERATION_MODE_COMMAND_TOPIC, payload)

        if self._optimistic or self._topic[CONF_OPERATION_MODE_STATE_TOPIC] is None:
            self._attr_current_operation = operation_mode
            self.async_write_ha_state()
