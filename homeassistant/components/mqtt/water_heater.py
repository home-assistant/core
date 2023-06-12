"""Support for MQTT water heater devices."""
from __future__ import annotations

import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import water_heater
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
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
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_conversion import TemperatureConverter

from .climate import MqttTemperatureControlEntity
from .config import DEFAULT_RETAIN, MQTT_BASE_SCHEMA
from .const import (
    CONF_CURRENT_TEMP_TEMPLATE,
    CONF_CURRENT_TEMP_TOPIC,
    CONF_MODE_COMMAND_TEMPLATE,
    CONF_MODE_COMMAND_TOPIC,
    CONF_MODE_LIST,
    CONF_MODE_STATE_TEMPLATE,
    CONF_MODE_STATE_TOPIC,
    CONF_PRECISION,
    CONF_RETAIN,
    CONF_TEMP_COMMAND_TEMPLATE,
    CONF_TEMP_COMMAND_TOPIC,
    CONF_TEMP_INITIAL,
    CONF_TEMP_MAX,
    CONF_TEMP_MIN,
    CONF_TEMP_STATE_TEMPLATE,
    CONF_TEMP_STATE_TOPIC,
    DEFAULT_OPTIMISTIC,
)
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, async_setup_entry_helper
from .models import MqttCommandTemplate, MqttValueTemplate, ReceiveMessage
from .util import get_mqtt_data, valid_publish_topic, valid_subscribe_topic

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
}


TOPIC_KEYS = (
    CONF_CURRENT_TEMP_TOPIC,
    CONF_MODE_COMMAND_TOPIC,
    CONF_MODE_STATE_TOPIC,
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
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_ON, default="ON"): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default="OFF"): cv.string,
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


class MqttWaterHeater(MqttTemperatureControlEntity, WaterHeaterEntity):
    """Representation of an MQTT water heater device."""

    _entity_id_format = water_heater.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_WATER_HEATER_ATTRIBUTES_BLOCKED

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the water heater device."""
        MqttTemperatureControlEntity.__init__(
            self, hass, config, config_entry, discovery_data
        )

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
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        @callback
        @log_messages(self.hass, self.entity_id)
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
        await super().async_set_temperature(**kwargs)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        payload = self._command_templates[CONF_MODE_COMMAND_TEMPLATE](operation_mode)
        await self._publish(CONF_MODE_COMMAND_TOPIC, payload)

        if self._optimistic or self._topic[CONF_MODE_STATE_TOPIC] is None:
            self._attr_current_operation = operation_mode
            self.async_write_ha_state()
