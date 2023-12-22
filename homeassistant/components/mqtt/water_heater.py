"""Support for MQTT water heater devices."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import water_heater
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
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
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import TemperatureConverter

from . import subscription
from .config import DEFAULT_RETAIN, MQTT_BASE_SCHEMA
from .const import (
    CONF_CURRENT_TEMP_TEMPLATE,
    CONF_CURRENT_TEMP_TOPIC,
    CONF_ENCODING,
    CONF_MODE_COMMAND_TEMPLATE,
    CONF_MODE_COMMAND_TOPIC,
    CONF_MODE_LIST,
    CONF_MODE_STATE_TEMPLATE,
    CONF_MODE_STATE_TOPIC,
    CONF_POWER_COMMAND_TEMPLATE,
    CONF_POWER_COMMAND_TOPIC,
    CONF_PRECISION,
    CONF_QOS,
    CONF_RETAIN,
    CONF_TEMP_COMMAND_TEMPLATE,
    CONF_TEMP_COMMAND_TOPIC,
    CONF_TEMP_INITIAL,
    CONF_TEMP_MAX,
    CONF_TEMP_MIN,
    CONF_TEMP_STATE_TEMPLATE,
    CONF_TEMP_STATE_TOPIC,
    DEFAULT_OPTIMISTIC,
    PAYLOAD_NONE,
)
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_setup_entity_entry_helper,
    write_state_on_attr_change,
)
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Water Heater"

MQTT_WATER_HEATER_ATTRIBUTES_BLOCKED = frozenset(
    {
        water_heater.ATTR_CURRENT_TEMPERATURE,
        water_heater.ATTR_MAX_TEMP,
        water_heater.ATTR_MIN_TEMP,
        water_heater.ATTR_TEMPERATURE,
        water_heater.ATTR_OPERATION_LIST,
        water_heater.ATTR_OPERATION_MODE,
    }
)

VALUE_TEMPLATE_KEYS = (
    CONF_CURRENT_TEMP_TEMPLATE,
    CONF_MODE_STATE_TEMPLATE,
    CONF_TEMP_STATE_TEMPLATE,
)

COMMAND_TEMPLATE_KEYS = {
    CONF_MODE_COMMAND_TEMPLATE,
    CONF_TEMP_COMMAND_TEMPLATE,
    CONF_POWER_COMMAND_TEMPLATE,
}


TOPIC_KEYS = (
    CONF_CURRENT_TEMP_TOPIC,
    CONF_MODE_COMMAND_TOPIC,
    CONF_MODE_STATE_TOPIC,
    CONF_POWER_COMMAND_TOPIC,
    CONF_TEMP_COMMAND_TOPIC,
    CONF_TEMP_STATE_TOPIC,
)


_PLATFORM_SCHEMA_BASE = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_CURRENT_TEMP_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_TEMP_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_MODE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_MODE_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(
            CONF_MODE_LIST,
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
        vol.Optional(CONF_MODE_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_MODE_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_ON, default="ON"): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default="OFF"): cv.string,
        vol.Optional(CONF_POWER_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_POWER_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_TEMP_INITIAL): cv.positive_int,
        vol.Optional(CONF_TEMP_MIN): vol.Coerce(float),
        vol.Optional(CONF_TEMP_MAX): vol.Coerce(float),
        vol.Optional(CONF_TEMP_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_TEMP_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = vol.All(
    _PLATFORM_SCHEMA_BASE,
)

_DISCOVERY_SCHEMA_BASE = _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA)

DISCOVERY_SCHEMA = vol.All(
    _DISCOVERY_SCHEMA_BASE,
)

# Support for CONF_POWER_STATE_TOPIC and CONF_POWER_STATE_TEMPLATE
# was removed in HA Core 2023.8
CONF_POWER_STATE_TEMPLATE = "power_state_template"
CONF_POWER_STATE_TOPIC = "power_state_topic"
CONF_PRESET_MODE_STATE_TOPIC = "preset_mode_state_topic"
CONF_PRESET_MODE_COMMAND_TOPIC = "preset_mode_command_topic"
CONF_PRESET_MODE_VALUE_TEMPLATE = "preset_mode_value_template"
CONF_PRESET_MODE_COMMAND_TEMPLATE = "preset_mode_command_template"
CONF_PRESET_MODES_LIST = "preset_modes"
CONF_SWING_MODE_COMMAND_TEMPLATE = "swing_mode_command_template"
CONF_SWING_MODE_COMMAND_TOPIC = "swing_mode_command_topic"
CONF_SWING_MODE_LIST = "swing_modes"
CONF_SWING_MODE_STATE_TEMPLATE = "swing_mode_state_template"
CONF_SWING_MODE_STATE_TOPIC = "swing_mode_state_topic"
CONF_TEMP_HIGH_COMMAND_TEMPLATE = "temperature_high_command_template"
CONF_TEMP_HIGH_COMMAND_TOPIC = "temperature_high_command_topic"
CONF_TEMP_HIGH_STATE_TEMPLATE = "temperature_high_state_template"
CONF_TEMP_HIGH_STATE_TOPIC = "temperature_high_state_topic"
CONF_TEMP_LOW_COMMAND_TEMPLATE = "temperature_low_command_template"
CONF_TEMP_LOW_COMMAND_TOPIC = "temperature_low_command_topic"
CONF_TEMP_LOW_STATE_TEMPLATE = "temperature_low_state_template"
CONF_TEMP_LOW_STATE_TOPIC = "temperature_low_state_topic"
CONF_TEMP_STEP = "temp_step"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT water heater device through YAML and through MQTT discovery."""
    await async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttWaterHeater,
        water_heater.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttWaterHeater(MqttEntity, WaterHeaterEntity):
    """Representation of an MQTT water heater device."""

    _default_name = DEFAULT_NAME
    _entity_id_format = water_heater.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_WATER_HEATER_ATTRIBUTES_BLOCKED

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_operation_list = config[CONF_MODE_LIST]
        self._attr_temperature_unit = config.get(
            CONF_TEMPERATURE_UNIT, self.hass.config.units.temperature_unit
        )
        if (min_temp := config.get(CONF_TEMP_MIN)) is not None:
            self._attr_min_temp = min_temp
        if (max_temp := config.get(CONF_TEMP_MAX)) is not None:
            self._attr_max_temp = max_temp
        if (precision := config.get(CONF_PRECISION)) is not None:
            self._attr_precision = precision

        self._topic = {key: config.get(key) for key in TOPIC_KEYS}

        self._optimistic = config[CONF_OPTIMISTIC]

        # Set init temp, if it is missing convert the default to the temperature units
        init_temp: float = config.get(
            CONF_TEMP_INITIAL,
            TemperatureConverter.convert(
                DEFAULT_MIN_TEMP,
                UnitOfTemperature.FAHRENHEIT,
                self.temperature_unit,
            ),
        )
        if self._topic[CONF_TEMP_STATE_TOPIC] is None or self._optimistic:
            self._attr_target_temperature = init_temp
        if self._topic[CONF_MODE_STATE_TOPIC] is None or self._optimistic:
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

        if (self._topic[CONF_MODE_STATE_TOPIC] is not None) or (
            self._topic[CONF_MODE_COMMAND_TOPIC] is not None
        ):
            support |= WaterHeaterEntityFeature.OPERATION_MODE

        if self._topic[CONF_POWER_COMMAND_TOPIC] is not None:
            support |= WaterHeaterEntityFeature.ON_OFF

        self._attr_supported_features = support

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        topics: dict[str, dict[str, Any]] = {}

        @callback
        def handle_mode_received(
            msg: ReceiveMessage, template_name: str, attr: str, mode_list: str
        ) -> None:
            """Handle receiving listed mode via MQTT."""
            payload = self.render_template(msg, template_name)

            if payload not in self._config[mode_list]:
                _LOGGER.error("Invalid %s mode: %s", mode_list, payload)
            else:
                setattr(self, attr, payload)

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_current_operation"})
        def handle_current_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving operation mode via MQTT."""
            handle_mode_received(
                msg,
                CONF_MODE_STATE_TEMPLATE,
                "_attr_current_operation",
                CONF_MODE_LIST,
            )

        self.add_subscription(
            topics, CONF_MODE_STATE_TOPIC, handle_current_mode_received
        )

        self.prepare_subscribe_topics(topics)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        operation_mode: str | None
        if (operation_mode := kwargs.get(ATTR_OPERATION_MODE)) is not None:
            await self.async_set_operation_mode(operation_mode)
        await self._async_set_temperature(**kwargs)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        payload = self._command_templates[CONF_MODE_COMMAND_TEMPLATE](operation_mode)
        await self._publish(CONF_MODE_COMMAND_TOPIC, payload)

        if self._optimistic or self._topic[CONF_MODE_STATE_TOPIC] is None:
            self._attr_current_operation = operation_mode
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if CONF_POWER_COMMAND_TOPIC in self._config:
            mqtt_payload = self._command_templates[CONF_POWER_COMMAND_TEMPLATE](
                self._config[CONF_PAYLOAD_ON]
            )
            await self._publish(CONF_POWER_COMMAND_TOPIC, mqtt_payload)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if CONF_POWER_COMMAND_TOPIC in self._config:
            mqtt_payload = self._command_templates[CONF_POWER_COMMAND_TEMPLATE](
                self._config[CONF_PAYLOAD_OFF]
            )
            await self._publish(CONF_POWER_COMMAND_TOPIC, mqtt_payload)

    def add_subscription(
        self,
        topics: dict[str, dict[str, Any]],
        topic: str,
        msg_callback: Callable[[ReceiveMessage], None],
    ) -> None:
        """Add a subscription."""
        qos: int = self._config[CONF_QOS]
        if topic in self._topic and self._topic[topic] is not None:
            topics[topic] = {
                "topic": self._topic[topic],
                "msg_callback": msg_callback,
                "qos": qos,
                "encoding": self._config[CONF_ENCODING] or None,
            }

    def render_template(
        self, msg: ReceiveMessage, template_name: str
    ) -> ReceivePayloadType:
        """Render a template by name."""
        template = self._value_templates[template_name]
        return template(msg.payload)

    @callback
    def handle_climate_attribute_received(
        self, msg: ReceiveMessage, template_name: str, attr: str
    ) -> None:
        """Handle climate attributes coming via MQTT."""
        payload = self.render_template(msg, template_name)
        if not payload:
            _LOGGER.debug(
                "Invalid empty payload for attribute %s, ignoring update",
                attr,
            )
            return
        if payload == PAYLOAD_NONE:
            setattr(self, attr, None)
            return
        try:
            setattr(self, attr, float(payload))
        except ValueError:
            _LOGGER.error("Could not parse %s from %s", template_name, payload)

    def prepare_subscribe_topics(  # noqa: C901
        self,
        topics: dict[str, dict[str, Any]],
    ) -> None:
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_current_temperature"})
        def handle_current_temperature_received(msg: ReceiveMessage) -> None:
            """Handle current temperature coming via MQTT."""
            self.handle_climate_attribute_received(
                msg, CONF_CURRENT_TEMP_TEMPLATE, "_attr_current_temperature"
            )

        self.add_subscription(
            topics, CONF_CURRENT_TEMP_TOPIC, handle_current_temperature_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_target_temperature"})
        def handle_target_temperature_received(msg: ReceiveMessage) -> None:
            """Handle target temperature coming via MQTT."""
            self.handle_climate_attribute_received(
                msg, CONF_TEMP_STATE_TEMPLATE, "_attr_target_temperature"
            )

        self.add_subscription(
            topics, CONF_TEMP_STATE_TOPIC, handle_target_temperature_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_target_temperature_low"})
        def handle_temperature_low_received(msg: ReceiveMessage) -> None:
            """Handle target temperature low coming via MQTT."""
            self.handle_climate_attribute_received(
                msg, CONF_TEMP_LOW_STATE_TEMPLATE, "_attr_target_temperature_low"
            )

        self.add_subscription(
            topics, CONF_TEMP_LOW_STATE_TOPIC, handle_temperature_low_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_target_temperature_high"})
        def handle_temperature_high_received(msg: ReceiveMessage) -> None:
            """Handle target temperature high coming via MQTT."""
            self.handle_climate_attribute_received(
                msg, CONF_TEMP_HIGH_STATE_TEMPLATE, "_attr_target_temperature_high"
            )

        self.add_subscription(
            topics, CONF_TEMP_HIGH_STATE_TOPIC, handle_temperature_high_received
        )

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    async def _publish(self, topic: str, payload: PublishPayloadType) -> None:
        if (topic_ := self._topic[topic]) is not None:
            await self.async_publish(
                topic_,
                payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
                self._config[CONF_ENCODING],
            )

    async def _set_climate_attribute(
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

    async def _async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        changed = await self._set_climate_attribute(
            kwargs.get(ATTR_TEMPERATURE),
            CONF_TEMP_COMMAND_TOPIC,
            CONF_TEMP_COMMAND_TEMPLATE,
            CONF_TEMP_STATE_TOPIC,
            "_attr_target_temperature",
        )

        changed |= await self._set_climate_attribute(
            kwargs.get(ATTR_TARGET_TEMP_LOW),
            CONF_TEMP_LOW_COMMAND_TOPIC,
            CONF_TEMP_LOW_COMMAND_TEMPLATE,
            CONF_TEMP_LOW_STATE_TOPIC,
            "_attr_target_temperature_low",
        )

        changed |= await self._set_climate_attribute(
            kwargs.get(ATTR_TARGET_TEMP_HIGH),
            CONF_TEMP_HIGH_COMMAND_TOPIC,
            CONF_TEMP_HIGH_COMMAND_TEMPLATE,
            CONF_TEMP_HIGH_STATE_TOPIC,
            "_attr_target_temperature_high",
        )

        if not changed:
            return
        self.async_write_ha_state()
