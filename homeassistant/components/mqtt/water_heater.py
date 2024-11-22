"""Support for MQTT water heater devices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

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
from homeassistant.helpers.typing import ConfigType, VolSchemaType
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
    CONF_POWER_COMMAND_TEMPLATE,
    CONF_POWER_COMMAND_TOPIC,
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
    PAYLOAD_NONE,
)
from .entity import async_setup_entity_entry_helper
from .models import MqttCommandTemplate, MqttValueTemplate, ReceiveMessage
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT water heater device through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttWaterHeater,
        water_heater.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttWaterHeater(MqttTemperatureControlEntity, WaterHeaterEntity):
    """Representation of an MQTT water heater device."""

    _default_name = DEFAULT_NAME
    _entity_id_format = water_heater.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_WATER_HEATER_ATTRIBUTES_BLOCKED
    _attr_target_temperature_low: float | None = None
    _attr_target_temperature_high: float | None = None

    @staticmethod
    def config_schema() -> VolSchemaType:
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

        value_templates: dict[str, Template | None] = {
            key: config.get(CONF_VALUE_TEMPLATE) for key in VALUE_TEMPLATE_KEYS
        }
        value_templates.update(
            {key: config[key] for key in VALUE_TEMPLATE_KEYS & config.keys()}
        )
        self._value_templates = {
            key: MqttValueTemplate(
                template, entity=self
            ).async_render_with_possible_json_value
            for key, template in value_templates.items()
        }

        self._command_templates = {
            key: MqttCommandTemplate(config.get(key), entity=self).async_render
            for key in COMMAND_TEMPLATE_KEYS
        }

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

    @callback
    def _handle_current_mode_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving operation mode via MQTT."""

        payload = self.render_template(msg, CONF_MODE_STATE_TEMPLATE)

        if not payload.strip():  # No output from template, ignore
            _LOGGER.debug(
                "Ignoring empty payload '%s' for current operation "
                "after rendering for topic %s",
                payload,
                msg.topic,
            )
            return

        if payload == PAYLOAD_NONE:
            self._attr_current_operation = None
        elif payload not in self._config[CONF_MODE_LIST]:
            _LOGGER.warning("Invalid %s mode: %s", CONF_MODE_LIST, payload)
        else:
            if TYPE_CHECKING:
                assert isinstance(payload, str)
            self._attr_current_operation = payload

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        # add subscriptions for WaterHeaterEntity
        self.add_subscription(
            CONF_MODE_STATE_TOPIC,
            self._handle_current_mode_received,
            {"_attr_current_operation"},
        )
        # add subscriptions for MqttTemperatureControlEntity
        self.prepare_subscribe_topics()

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
