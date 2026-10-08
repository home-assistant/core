"""Support for MQTT climate devices."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import partial
import logging
from typing import Any, override

import probatio

from homeassistant.components import climate
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_NONE,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityCapabilityAttribute,
    ClimateEntityFeature,
    ClimateEntityStateAttribute,
    HVACAction,
    HVACMode,
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
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import (
    UNDEFINED,
    ConfigType,
    UndefinedType,
    VolSchemaType,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from . import subscription
from .config import DEFAULT_RETAIN, MQTT_BASE_SCHEMA
from .const import (
    CONF_ACTION_TEMPLATE,
    CONF_ACTION_TOPIC,
    CONF_CURRENT_HUMIDITY_TEMPLATE,
    CONF_CURRENT_HUMIDITY_TOPIC,
    CONF_CURRENT_TEMP_TEMPLATE,
    CONF_CURRENT_TEMP_TOPIC,
    CONF_FAN_MODE_COMMAND_TEMPLATE,
    CONF_FAN_MODE_COMMAND_TOPIC,
    CONF_FAN_MODE_LIST,
    CONF_FAN_MODE_STATE_TEMPLATE,
    CONF_FAN_MODE_STATE_TOPIC,
    CONF_HUMIDITY_COMMAND_TEMPLATE,
    CONF_HUMIDITY_COMMAND_TOPIC,
    CONF_HUMIDITY_MAX,
    CONF_HUMIDITY_MIN,
    CONF_HUMIDITY_STATE_TEMPLATE,
    CONF_HUMIDITY_STATE_TOPIC,
    CONF_MODE_COMMAND_TEMPLATE,
    CONF_MODE_COMMAND_TOPIC,
    CONF_MODE_LIST,
    CONF_MODE_STATE_TEMPLATE,
    CONF_MODE_STATE_TOPIC,
    CONF_POWER_COMMAND_TEMPLATE,
    CONF_POWER_COMMAND_TOPIC,
    CONF_PRECISION,
    CONF_PRESET_MODE_COMMAND_TEMPLATE,
    CONF_PRESET_MODE_COMMAND_TOPIC,
    CONF_PRESET_MODE_STATE_TOPIC,
    CONF_PRESET_MODE_VALUE_TEMPLATE,
    CONF_PRESET_MODES_LIST,
    CONF_RETAIN,
    CONF_SWING_HORIZONTAL_MODE_COMMAND_TEMPLATE,
    CONF_SWING_HORIZONTAL_MODE_COMMAND_TOPIC,
    CONF_SWING_HORIZONTAL_MODE_LIST,
    CONF_SWING_HORIZONTAL_MODE_STATE_TEMPLATE,
    CONF_SWING_HORIZONTAL_MODE_STATE_TOPIC,
    CONF_SWING_MODE_COMMAND_TEMPLATE,
    CONF_SWING_MODE_COMMAND_TOPIC,
    CONF_SWING_MODE_LIST,
    CONF_SWING_MODE_STATE_TEMPLATE,
    CONF_SWING_MODE_STATE_TOPIC,
    CONF_TEMP_COMMAND_TEMPLATE,
    CONF_TEMP_COMMAND_TOPIC,
    CONF_TEMP_HIGH_COMMAND_TEMPLATE,
    CONF_TEMP_HIGH_COMMAND_TOPIC,
    CONF_TEMP_HIGH_STATE_TEMPLATE,
    CONF_TEMP_HIGH_STATE_TOPIC,
    CONF_TEMP_INITIAL,
    CONF_TEMP_LOW_COMMAND_TEMPLATE,
    CONF_TEMP_LOW_COMMAND_TOPIC,
    CONF_TEMP_LOW_STATE_TEMPLATE,
    CONF_TEMP_LOW_STATE_TOPIC,
    CONF_TEMP_MAX,
    CONF_TEMP_MIN,
    CONF_TEMP_STATE_TEMPLATE,
    CONF_TEMP_STATE_TOPIC,
    CONF_TEMP_STEP,
    DEFAULT_CLIMATE_INITIAL_TEMPERATURE,
    DEFAULT_OPTIMISTIC,
    PAYLOAD_NONE,
)
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
)
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

DEFAULT_NAME = "MQTT HVAC"

MQTT_CLIMATE_ATTRIBUTES_BLOCKED = frozenset(
    {
        ClimateEntityCapabilityAttribute.FAN_MODES,
        ClimateEntityCapabilityAttribute.HVAC_MODES,
        ClimateEntityCapabilityAttribute.MAX_HUMIDITY,
        ClimateEntityCapabilityAttribute.MAX_TEMP,
        ClimateEntityCapabilityAttribute.MIN_HUMIDITY,
        ClimateEntityCapabilityAttribute.MIN_TEMP,
        ClimateEntityCapabilityAttribute.PRESET_MODES,
        ClimateEntityCapabilityAttribute.SWING_HORIZONTAL_MODES,
        ClimateEntityCapabilityAttribute.SWING_MODES,
        ClimateEntityCapabilityAttribute.TARGET_TEMP_STEP,
        ClimateEntityStateAttribute.CURRENT_HUMIDITY,
        ClimateEntityStateAttribute.CURRENT_TEMPERATURE,
        ClimateEntityStateAttribute.FAN_MODE,
        ClimateEntityStateAttribute.HVAC_ACTION,
        ClimateEntityStateAttribute.PRESET_MODE,
        ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE,
        ClimateEntityStateAttribute.SWING_MODE,
        ClimateEntityStateAttribute.TARGET_HUMIDITY,
        ClimateEntityStateAttribute.TARGET_TEMPERATURE,
        ClimateEntityStateAttribute.TARGET_TEMP_HIGH,
        ClimateEntityStateAttribute.TARGET_TEMP_LOW,
    }
)

VALUE_TEMPLATE_KEYS = (
    CONF_CURRENT_HUMIDITY_TEMPLATE,
    CONF_CURRENT_TEMP_TEMPLATE,
    CONF_FAN_MODE_STATE_TEMPLATE,
    CONF_HUMIDITY_STATE_TEMPLATE,
    CONF_MODE_STATE_TEMPLATE,
    CONF_ACTION_TEMPLATE,
    CONF_PRESET_MODE_VALUE_TEMPLATE,
    CONF_SWING_HORIZONTAL_MODE_STATE_TEMPLATE,
    CONF_SWING_MODE_STATE_TEMPLATE,
    CONF_TEMP_HIGH_STATE_TEMPLATE,
    CONF_TEMP_LOW_STATE_TEMPLATE,
    CONF_TEMP_STATE_TEMPLATE,
)

COMMAND_TEMPLATE_KEYS = {
    CONF_FAN_MODE_COMMAND_TEMPLATE,
    CONF_HUMIDITY_COMMAND_TEMPLATE,
    CONF_MODE_COMMAND_TEMPLATE,
    CONF_POWER_COMMAND_TEMPLATE,
    CONF_PRESET_MODE_COMMAND_TEMPLATE,
    CONF_SWING_HORIZONTAL_MODE_COMMAND_TEMPLATE,
    CONF_SWING_MODE_COMMAND_TEMPLATE,
    CONF_TEMP_COMMAND_TEMPLATE,
    CONF_TEMP_HIGH_COMMAND_TEMPLATE,
    CONF_TEMP_LOW_COMMAND_TEMPLATE,
}


TOPIC_KEYS = (
    CONF_ACTION_TOPIC,
    CONF_CURRENT_HUMIDITY_TOPIC,
    CONF_CURRENT_TEMP_TOPIC,
    CONF_FAN_MODE_COMMAND_TOPIC,
    CONF_FAN_MODE_STATE_TOPIC,
    CONF_HUMIDITY_COMMAND_TOPIC,
    CONF_HUMIDITY_STATE_TOPIC,
    CONF_MODE_COMMAND_TOPIC,
    CONF_MODE_STATE_TOPIC,
    CONF_POWER_COMMAND_TOPIC,
    CONF_PRESET_MODE_COMMAND_TOPIC,
    CONF_PRESET_MODE_STATE_TOPIC,
    CONF_SWING_HORIZONTAL_MODE_COMMAND_TOPIC,
    CONF_SWING_HORIZONTAL_MODE_STATE_TOPIC,
    CONF_SWING_MODE_COMMAND_TOPIC,
    CONF_SWING_MODE_STATE_TOPIC,
    CONF_TEMP_COMMAND_TOPIC,
    CONF_TEMP_HIGH_COMMAND_TOPIC,
    CONF_TEMP_HIGH_STATE_TOPIC,
    CONF_TEMP_LOW_COMMAND_TOPIC,
    CONF_TEMP_LOW_STATE_TOPIC,
    CONF_TEMP_STATE_TOPIC,
)


def valid_preset_mode_configuration(config: ConfigType) -> ConfigType:
    """Validate that the preset mode reset payload is not one of the preset modes."""
    if PRESET_NONE in config[CONF_PRESET_MODES_LIST]:
        raise probatio.Invalid("preset_modes must not include preset mode 'none'")
    return config


def valid_humidity_range_configuration(config: ConfigType) -> ConfigType:
    """Validate a target_humidity range configuration, throws otherwise."""
    if config[CONF_HUMIDITY_MIN] >= config[CONF_HUMIDITY_MAX]:
        raise probatio.Invalid("target_humidity_max must be > target_humidity_min")
    if config[CONF_HUMIDITY_MAX] > 100:
        raise probatio.Invalid("max_humidity must be <= 100")

    return config


def valid_humidity_state_configuration(config: ConfigType) -> ConfigType:
    """Validate humidity state.

    Ensure that if CONF_HUMIDITY_STATE_TOPIC is set then
    CONF_HUMIDITY_COMMAND_TOPIC is also set.
    """
    if (
        CONF_HUMIDITY_STATE_TOPIC in config
        and CONF_HUMIDITY_COMMAND_TOPIC not in config
    ):
        raise probatio.Invalid(
            f"{CONF_HUMIDITY_STATE_TOPIC} cannot be used without"
            f" {CONF_HUMIDITY_COMMAND_TOPIC}"
        )

    return config


_PLATFORM_SCHEMA_BASE = MQTT_BASE_SCHEMA.extend(
    {
        probatio.Optional(CONF_CURRENT_HUMIDITY_TEMPLATE): cv.template,
        probatio.Optional(CONF_CURRENT_HUMIDITY_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_CURRENT_TEMP_TEMPLATE): cv.template,
        probatio.Optional(CONF_CURRENT_TEMP_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_FAN_MODE_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(CONF_FAN_MODE_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(
            CONF_FAN_MODE_LIST,
            default=[FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
        ): probatio.EnsureList(),
        probatio.Optional(CONF_FAN_MODE_STATE_TEMPLATE): cv.template,
        probatio.Optional(CONF_FAN_MODE_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_HUMIDITY_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(CONF_HUMIDITY_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(
            CONF_HUMIDITY_MIN, default=DEFAULT_MIN_HUMIDITY
        ): cv.positive_float,
        probatio.Optional(
            CONF_HUMIDITY_MAX, default=DEFAULT_MAX_HUMIDITY
        ): cv.positive_float,
        probatio.Optional(CONF_HUMIDITY_STATE_TEMPLATE): cv.template,
        probatio.Optional(CONF_HUMIDITY_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_MODE_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(CONF_MODE_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(
            CONF_MODE_LIST,
            default=[
                HVACMode.AUTO,
                HVACMode.OFF,
                HVACMode.COOL,
                HVACMode.HEAT,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
            ],
        ): probatio.EnsureList(),
        probatio.Optional(CONF_MODE_STATE_TEMPLATE): cv.template,
        probatio.Optional(CONF_MODE_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_NAME): probatio.Any(cv.string, None),
        probatio.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        probatio.Optional(CONF_PAYLOAD_ON, default="ON"): cv.string,
        probatio.Optional(CONF_PAYLOAD_OFF, default="OFF"): cv.string,
        probatio.Optional(CONF_POWER_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_POWER_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(CONF_PRECISION): probatio.All(
            probatio.Coerce(float),
            probatio.In([PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]),
        ),
        probatio.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        probatio.Optional(CONF_ACTION_TEMPLATE): cv.template,
        probatio.Optional(CONF_ACTION_TOPIC): valid_subscribe_topic,
        # CONF_PRESET_MODE_COMMAND_TOPIC and CONF_PRESET_MODES_LIST
        # must be used together
        probatio.Inclusive(
            CONF_PRESET_MODE_COMMAND_TOPIC, "preset_modes"
        ): valid_publish_topic,
        probatio.Inclusive(
            CONF_PRESET_MODES_LIST, "preset_modes", default=[]
        ): probatio.EnsureList(),
        probatio.Optional(CONF_PRESET_MODE_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(CONF_PRESET_MODE_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_PRESET_MODE_VALUE_TEMPLATE): cv.template,
        probatio.Optional(CONF_SWING_HORIZONTAL_MODE_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(
            CONF_SWING_HORIZONTAL_MODE_COMMAND_TOPIC
        ): valid_publish_topic,
        probatio.Optional(
            CONF_SWING_HORIZONTAL_MODE_LIST, default=[SWING_ON, SWING_OFF]
        ): probatio.EnsureList(),
        probatio.Optional(CONF_SWING_HORIZONTAL_MODE_STATE_TEMPLATE): cv.template,
        probatio.Optional(
            CONF_SWING_HORIZONTAL_MODE_STATE_TOPIC
        ): valid_subscribe_topic,
        probatio.Optional(CONF_SWING_MODE_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(CONF_SWING_MODE_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(
            CONF_SWING_MODE_LIST, default=[SWING_ON, SWING_OFF]
        ): probatio.EnsureList(),
        probatio.Optional(CONF_SWING_MODE_STATE_TEMPLATE): cv.template,
        probatio.Optional(CONF_SWING_MODE_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_TEMP_INITIAL): probatio.All(probatio.Coerce(float)),
        probatio.Optional(CONF_TEMP_MIN): probatio.Coerce(float),
        probatio.Optional(CONF_TEMP_MAX): probatio.Coerce(float),
        probatio.Optional(CONF_TEMP_STEP, default=1.0): probatio.Coerce(float),
        probatio.Optional(CONF_TEMP_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(CONF_TEMP_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_TEMP_HIGH_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(CONF_TEMP_HIGH_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_TEMP_HIGH_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_TEMP_HIGH_STATE_TEMPLATE): cv.template,
        probatio.Optional(CONF_TEMP_LOW_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(CONF_TEMP_LOW_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_TEMP_LOW_STATE_TEMPLATE): cv.template,
        probatio.Optional(CONF_TEMP_LOW_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_TEMP_STATE_TEMPLATE): cv.template,
        probatio.Optional(CONF_TEMP_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
        probatio.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = probatio.All(
    _PLATFORM_SCHEMA_BASE,
    valid_preset_mode_configuration,
    valid_humidity_range_configuration,
    valid_humidity_state_configuration,
)

_DISCOVERY_SCHEMA_BASE = _PLATFORM_SCHEMA_BASE.extend({}, extra=probatio.REMOVE_EXTRA)

DISCOVERY_SCHEMA = probatio.All(
    _DISCOVERY_SCHEMA_BASE,
    valid_preset_mode_configuration,
    valid_humidity_range_configuration,
    valid_humidity_state_configuration,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT climate through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttClimate,
        climate.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttTemperatureControlEntity(MqttEntity, ABC):
    """Helper entity class to control temperature.

    MqttTemperatureControlEntity supports shared methods for
    climate and water_heater platforms.
    """

    _attr_current_temperature: float | None
    _attr_target_temperature: float | None
    _attr_target_temperature_low: float | None
    _attr_target_temperature_high: float | None

    _feature_preset_mode: bool = False
    _optimistic: bool
    _topic: dict[str, Any]

    _command_templates: dict[str, Callable[[PublishPayloadType], PublishPayloadType]]
    _value_templates: dict[str, Callable[[ReceivePayloadType], ReceivePayloadType]]

    def render_template(
        self, msg: ReceiveMessage, template_name: str
    ) -> ReceivePayloadType:
        """Render a template by name."""
        template = self._value_templates[template_name]
        return template(msg.payload)

    @callback
    def _parse_float_payload(
        self, msg: ReceiveMessage, template_name: str, name: str
    ) -> float | UndefinedType | None:
        """Render and parse a numeric payload, UNDEFINED means ignore the update."""
        payload = self.render_template(msg, template_name)
        if not payload:
            _LOGGER.debug(
                "Invalid empty payload for %s, ignoring update",
                name,
            )
            return UNDEFINED
        if payload == PAYLOAD_NONE:
            return None
        try:
            return float(payload)
        except ValueError:
            _LOGGER.error("Could not parse %s from %s", template_name, payload)
            return UNDEFINED

    @callback
    def _handle_current_temperature_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving the current temperature via MQTT."""
        if (
            value := self._parse_float_payload(
                msg, CONF_CURRENT_TEMP_TEMPLATE, "current temperature"
            )
        ) is not UNDEFINED:
            self._attr_current_temperature = value

    @override
    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    async def _publish(self, topic: str, payload: PublishPayloadType) -> None:
        if self._topic[topic] is not None:
            await self.async_publish_with_config(self._topic[topic], payload)

    @abstractmethod
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""


class MqttClimate(MqttTemperatureControlEntity, ClimateEntity):
    """Representation of an MQTT climate device."""

    _attr_fan_mode: str | None = None
    _attr_hvac_mode: HVACMode | None = None
    _attr_swing_horizontal_mode: str | None = None
    _attr_swing_mode: str | None = None
    _default_name = DEFAULT_NAME
    _entity_id_format = climate.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_CLIMATE_ATTRIBUTES_BLOCKED
    _attr_target_temperature_low: float | None = None
    _attr_target_temperature_high: float | None = None
    _single_and_range_setpoints: bool
    _parked_target_temperature: float | None = None
    _parked_target_temperature_range: tuple[float | None, float | None] = (None, None)

    @staticmethod
    @override
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    @override
    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_hvac_modes = config[CONF_MODE_LIST]
        self._single_and_range_setpoints = (
            HVACMode.HEAT_COOL in self._attr_hvac_modes
            and (
                HVACMode.HEAT in self._attr_hvac_modes
                or HVACMode.COOL in self._attr_hvac_modes
            )
        )
        # Make sure the min an max temp is converted to the correct when not set
        self._attr_temperature_unit = config.get(
            CONF_TEMPERATURE_UNIT, self.hass.config.units.temperature_unit
        )
        if (min_temp := config.get(CONF_TEMP_MIN)) is not None:
            self._attr_min_temp = min_temp
        if (max_temp := config.get(CONF_TEMP_MAX)) is not None:
            self._attr_max_temp = max_temp
        self._attr_min_humidity = config[CONF_HUMIDITY_MIN]
        self._attr_max_humidity = config[CONF_HUMIDITY_MAX]
        if (precision := config.get(CONF_PRECISION)) is not None:
            self._attr_precision = precision
        self._attr_fan_modes = config[CONF_FAN_MODE_LIST]
        self._attr_swing_horizontal_modes = config[CONF_SWING_HORIZONTAL_MODE_LIST]
        self._attr_swing_modes = config[CONF_SWING_MODE_LIST]
        self._attr_target_temperature_step = config[CONF_TEMP_STEP]

        self._topic = {key: config.get(key) for key in TOPIC_KEYS}

        self._optimistic = config[CONF_OPTIMISTIC]

        # Set init temp, if it is missing convert the default to the temperature units
        init_temp: float = config.get(
            CONF_TEMP_INITIAL,
            TemperatureConverter.convert(
                DEFAULT_CLIMATE_INITIAL_TEMPERATURE,
                UnitOfTemperature.CELSIUS,
                self.temperature_unit,
            ),
        )
        if self._topic[CONF_TEMP_STATE_TOPIC] is None or self._optimistic:
            self._attr_target_temperature = init_temp
        if self._topic[CONF_TEMP_LOW_STATE_TOPIC] is None or self._optimistic:
            self._attr_target_temperature_low = init_temp
        if self._topic[CONF_TEMP_HIGH_STATE_TOPIC] is None or self._optimistic:
            self._attr_target_temperature_high = init_temp

        if self._topic[CONF_FAN_MODE_STATE_TOPIC] is None or self._optimistic:
            self._attr_fan_mode = FAN_LOW
        if (
            self._topic[CONF_SWING_HORIZONTAL_MODE_STATE_TOPIC] is None
            or self._optimistic
        ):
            self._attr_swing_horizontal_mode = SWING_OFF
        if self._topic[CONF_SWING_MODE_STATE_TOPIC] is None or self._optimistic:
            self._attr_swing_mode = SWING_OFF
        if self._topic[CONF_MODE_STATE_TOPIC] is None or self._optimistic:
            self._attr_hvac_mode = HVACMode.OFF
        self._feature_preset_mode = CONF_PRESET_MODE_COMMAND_TOPIC in config
        if self._feature_preset_mode:
            presets = []
            presets.extend(config[CONF_PRESET_MODES_LIST])
            if presets:
                presets.insert(0, PRESET_NONE)
            self._attr_preset_modes = presets
            self._attr_preset_mode = PRESET_NONE
        else:
            self._attr_preset_modes = []
        self._optimistic_preset_mode = (
            self._optimistic or CONF_PRESET_MODE_STATE_TOPIC not in config
        )

        value_templates: dict[str, Template | None] = {
            key: config.get(CONF_VALUE_TEMPLATE) for key in VALUE_TEMPLATE_KEYS
        }
        value_templates.update(
            {key: config[key] for key in VALUE_TEMPLATE_KEYS & config.keys()}
        )
        self._value_templates = {
            key: MqttValueTemplate(
                template,
                entity=self,
            ).async_render_with_possible_json_value
            for key, template in value_templates.items()
        }

        self._command_templates = {
            key: MqttCommandTemplate(config.get(key), entity=self).async_render
            for key in COMMAND_TEMPLATE_KEYS
        }

        support = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if (self._topic[CONF_TEMP_STATE_TOPIC] is not None) or (
            self._topic[CONF_TEMP_COMMAND_TOPIC] is not None
        ):
            support |= ClimateEntityFeature.TARGET_TEMPERATURE

        if (self._topic[CONF_TEMP_LOW_STATE_TOPIC] is not None) or (
            self._topic[CONF_TEMP_LOW_COMMAND_TOPIC] is not None
        ):
            support |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

        if (self._topic[CONF_TEMP_HIGH_STATE_TOPIC] is not None) or (
            self._topic[CONF_TEMP_HIGH_COMMAND_TOPIC] is not None
        ):
            support |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

        if self._topic[CONF_HUMIDITY_COMMAND_TOPIC] is not None:
            support |= ClimateEntityFeature.TARGET_HUMIDITY

        if (self._topic[CONF_FAN_MODE_STATE_TOPIC] is not None) or (
            self._topic[CONF_FAN_MODE_COMMAND_TOPIC] is not None
        ):
            support |= ClimateEntityFeature.FAN_MODE

        if (self._topic[CONF_SWING_HORIZONTAL_MODE_STATE_TOPIC] is not None) or (
            self._topic[CONF_SWING_HORIZONTAL_MODE_COMMAND_TOPIC] is not None
        ):
            support |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

        if (self._topic[CONF_SWING_MODE_STATE_TOPIC] is not None) or (
            self._topic[CONF_SWING_MODE_COMMAND_TOPIC] is not None
        ):
            support |= ClimateEntityFeature.SWING_MODE

        if self._feature_preset_mode:
            support |= ClimateEntityFeature.PRESET_MODE

        self._attr_supported_features = support

    @callback
    def _handle_action_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving action via MQTT."""
        payload = self.render_template(msg, CONF_ACTION_TEMPLATE)
        if not payload:
            _LOGGER.debug(
                "Invalid %s action: %s, ignoring",
                [e.value for e in HVACAction],
                payload,
            )
            return
        if payload == PAYLOAD_NONE:
            self._attr_hvac_action = None
            return
        try:
            self._attr_hvac_action = HVACAction(str(payload))
        except ValueError:
            _LOGGER.warning(
                "Invalid %s action: %s",
                [e.value for e in HVACAction],
                payload,
            )
            return

    @callback
    def _handle_mode_received(
        self, template_name: str, attr: str, mode_list: str, msg: ReceiveMessage
    ) -> None:
        """Handle receiving listed mode via MQTT."""
        payload = self.render_template(msg, template_name)

        if payload == PAYLOAD_NONE:
            setattr(self, attr, None)
        elif payload not in self._config[mode_list]:
            _LOGGER.warning("Invalid %s mode: %s", mode_list, payload)
        else:
            setattr(self, attr, payload)

    @callback
    def _handle_preset_mode_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving preset mode via MQTT."""
        preset_mode = self.render_template(msg, CONF_PRESET_MODE_VALUE_TEMPLATE)
        if preset_mode in [PRESET_NONE, PAYLOAD_NONE]:
            self._attr_preset_mode = PRESET_NONE
            return
        if not preset_mode:
            _LOGGER.debug("Ignoring empty preset_mode from '%s'", msg.topic)
            return
        if not self._attr_preset_modes or preset_mode not in self._attr_preset_modes:
            _LOGGER.warning(
                "'%s' received on topic %s. '%s' is not a valid preset mode",
                msg.payload,
                msg.topic,
                preset_mode,
            )
        else:
            self._attr_preset_mode = str(preset_mode)

    @callback
    def _handle_target_temperature_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving the target temperature via MQTT."""
        if (
            value := self._parse_float_payload(
                msg, CONF_TEMP_STATE_TEMPLATE, "target temperature"
            )
        ) is UNDEFINED:
            return
        self._attr_target_temperature = value
        if value is not None:
            self._park_range_setpoints()

    @callback
    def _handle_target_temperature_low_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving the target temperature low via MQTT."""
        if (
            value := self._parse_float_payload(
                msg, CONF_TEMP_LOW_STATE_TEMPLATE, "target temperature low"
            )
        ) is UNDEFINED:
            return
        self._attr_target_temperature_low = value
        if value is not None:
            self._park_single_setpoint()

    @callback
    def _handle_target_temperature_high_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving the target temperature high via MQTT."""
        if (
            value := self._parse_float_payload(
                msg, CONF_TEMP_HIGH_STATE_TEMPLATE, "target temperature high"
            )
        ) is UNDEFINED:
            return
        self._attr_target_temperature_high = value
        if value is not None:
            self._park_single_setpoint()

    @callback
    def _handle_current_humidity_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving the current humidity via MQTT."""
        if (
            value := self._parse_float_payload(
                msg, CONF_CURRENT_HUMIDITY_TEMPLATE, "current humidity"
            )
        ) is not UNDEFINED:
            self._attr_current_humidity = value

    @callback
    def _handle_target_humidity_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving the target humidity via MQTT."""
        if (
            value := self._parse_float_payload(
                msg, CONF_HUMIDITY_STATE_TEMPLATE, "target humidity"
            )
        ) is not UNDEFINED:
            self._attr_target_humidity = value

    @callback
    @override
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_ACTION_TOPIC,
            self._handle_action_received,
            {"_attr_hvac_action"},
        )
        self.add_subscription(
            CONF_CURRENT_HUMIDITY_TOPIC,
            self._handle_current_humidity_received,
            {"_attr_current_humidity"},
        )
        self.add_subscription(
            CONF_HUMIDITY_STATE_TOPIC,
            self._handle_target_humidity_received,
            {"_attr_target_humidity"},
        )
        self.add_subscription(
            CONF_MODE_STATE_TOPIC,
            partial(
                self._handle_mode_received,
                CONF_MODE_STATE_TEMPLATE,
                "_attr_hvac_mode",
                CONF_MODE_LIST,
            ),
            {"_attr_hvac_mode"},
        )
        self.add_subscription(
            CONF_FAN_MODE_STATE_TOPIC,
            partial(
                self._handle_mode_received,
                CONF_FAN_MODE_STATE_TEMPLATE,
                "_attr_fan_mode",
                CONF_FAN_MODE_LIST,
            ),
            {"_attr_fan_mode"},
        )
        self.add_subscription(
            CONF_SWING_HORIZONTAL_MODE_STATE_TOPIC,
            partial(
                self._handle_mode_received,
                CONF_SWING_HORIZONTAL_MODE_STATE_TEMPLATE,
                "_attr_swing_horizontal_mode",
                CONF_SWING_HORIZONTAL_MODE_LIST,
            ),
            {"_attr_swing_horizontal_mode"},
        )
        self.add_subscription(
            CONF_SWING_MODE_STATE_TOPIC,
            partial(
                self._handle_mode_received,
                CONF_SWING_MODE_STATE_TEMPLATE,
                "_attr_swing_mode",
                CONF_SWING_MODE_LIST,
            ),
            {"_attr_swing_mode"},
        )
        self.add_subscription(
            CONF_PRESET_MODE_STATE_TOPIC,
            self._handle_preset_mode_received,
            {"_attr_preset_mode"},
        )
        self.add_subscription(
            CONF_CURRENT_TEMP_TOPIC,
            self._handle_current_temperature_received,
            {"_attr_current_temperature"},
        )
        setpoints = {
            "_attr_target_temperature",
            "_attr_target_temperature_low",
            "_attr_target_temperature_high",
        }
        self.add_subscription(
            CONF_TEMP_STATE_TOPIC,
            self._handle_target_temperature_received,
            setpoints,
        )
        self.add_subscription(
            CONF_TEMP_LOW_STATE_TOPIC,
            self._handle_target_temperature_low_received,
            setpoints,
        )
        self.add_subscription(
            CONF_TEMP_HIGH_STATE_TOPIC,
            self._handle_target_temperature_high_received,
            setpoints,
        )

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        operation_mode: HVACMode | None
        if (operation_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(operation_mode)

        optimistic_update = False
        temperature: float | None
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            if self._optimistic or self._topic[CONF_TEMP_STATE_TOPIC] is None:
                optimistic_update = True
                self._attr_target_temperature = temperature
                # We reset low and high setpoints when a single setpoint is set
                self._park_range_setpoints()
            mqtt_payload = self._command_templates[CONF_TEMP_COMMAND_TEMPLATE](
                temperature
            )
            await self._publish(CONF_TEMP_COMMAND_TOPIC, mqtt_payload)

        target_temp_low: float | None
        if (target_temp_low := kwargs.get(ATTR_TARGET_TEMP_LOW)) is not None:
            if self._optimistic or self._topic[CONF_TEMP_LOW_STATE_TOPIC] is None:
                optimistic_update = True
                self._attr_target_temperature_low = target_temp_low
                # We reset the single setpoint when a setpoint range is set
                self._park_single_setpoint()
            mqtt_payload = self._command_templates[CONF_TEMP_LOW_COMMAND_TEMPLATE](
                target_temp_low
            )
            await self._publish(CONF_TEMP_LOW_COMMAND_TOPIC, mqtt_payload)

        target_temp_high: float | None
        if (target_temp_high := kwargs.get(ATTR_TARGET_TEMP_HIGH)) is not None:
            if self._optimistic or self._topic[CONF_TEMP_HIGH_STATE_TOPIC] is None:
                optimistic_update = True
                self._attr_target_temperature_high = target_temp_high
                self._park_single_setpoint()
            mqtt_payload = self._command_templates[CONF_TEMP_HIGH_COMMAND_TEMPLATE](
                target_temp_high
            )
            await self._publish(CONF_TEMP_HIGH_COMMAND_TOPIC, mqtt_payload)

        if optimistic_update:
            self.async_write_ha_state()

    @override
    async def async_set_humidity(self, humidity: float) -> None:
        """Set new target humidity."""
        mqtt_payload = self._command_templates[CONF_HUMIDITY_COMMAND_TEMPLATE](humidity)
        await self._publish(CONF_HUMIDITY_COMMAND_TOPIC, mqtt_payload)

        if self._optimistic or self._topic[CONF_HUMIDITY_STATE_TOPIC] is None:
            self._attr_target_humidity = humidity
            self.async_write_ha_state()

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new swing horizontal mode."""
        payload = self._command_templates[CONF_SWING_HORIZONTAL_MODE_COMMAND_TEMPLATE](
            swing_horizontal_mode
        )
        await self._publish(CONF_SWING_HORIZONTAL_MODE_COMMAND_TOPIC, payload)

        if (
            self._optimistic
            or self._topic[CONF_SWING_HORIZONTAL_MODE_STATE_TOPIC] is None
        ):
            self._attr_swing_horizontal_mode = swing_horizontal_mode
            self.async_write_ha_state()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        payload = self._command_templates[CONF_SWING_MODE_COMMAND_TEMPLATE](swing_mode)
        await self._publish(CONF_SWING_MODE_COMMAND_TOPIC, payload)

        if self._optimistic or self._topic[CONF_SWING_MODE_STATE_TOPIC] is None:
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target temperature."""
        payload = self._command_templates[CONF_FAN_MODE_COMMAND_TEMPLATE](fan_mode)
        await self._publish(CONF_FAN_MODE_COMMAND_TOPIC, payload)

        if self._optimistic or self._topic[CONF_FAN_MODE_STATE_TOPIC] is None:
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        payload = self._command_templates[CONF_MODE_COMMAND_TEMPLATE](hvac_mode)
        await self._publish(CONF_MODE_COMMAND_TOPIC, payload)

        if self._optimistic or self._topic[CONF_MODE_STATE_TOPIC] is None:
            self._attr_hvac_mode = hvac_mode
            self._swap_setpoints(hvac_mode)
            self.async_write_ha_state()

    def _park_single_setpoint(self) -> None:
        """Park and reset the single setpoint when a setpoint range is active."""
        if not self._single_and_range_setpoints or self.target_temperature is None:
            return
        self._parked_target_temperature = self.target_temperature
        self._attr_target_temperature = None

    def _park_range_setpoints(self) -> None:
        """Park and reset the setpoint range when a single setpoint is active."""
        temp_range = (self.target_temperature_low, self.target_temperature_high)
        if not self._single_and_range_setpoints or temp_range == (None, None):
            return
        self._parked_target_temperature_range = temp_range
        self._attr_target_temperature_low = None
        self._attr_target_temperature_high = None

    def _swap_setpoints(self, hvac_mode: HVACMode) -> None:
        """Swap optimistic single and range setpoints on an HVAC mode change.

        The inactive setpoints are parked, so they can be restored
        when switching back, as the device is expected to remember them.
        """
        if not self._single_and_range_setpoints or hvac_mode not in (
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.HEAT_COOL,
        ):
            return
        uses_range = hvac_mode is HVACMode.HEAT_COOL
        if self._optimistic or self._topic[CONF_TEMP_STATE_TOPIC] is None:
            if uses_range:
                self._park_single_setpoint()
            elif self.target_temperature is None:
                self._attr_target_temperature = self._parked_target_temperature
        if self._optimistic or (
            self._topic[CONF_TEMP_LOW_STATE_TOPIC] is None
            and self._topic[CONF_TEMP_HIGH_STATE_TOPIC] is None
        ):
            if not uses_range:
                self._park_range_setpoints()
            elif (
                self.target_temperature_low is None
                and self.target_temperature_high is None
            ):
                (
                    self._attr_target_temperature_low,
                    self._attr_target_temperature_high,
                ) = self._parked_target_temperature_range

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a preset mode."""
        mqtt_payload = self._command_templates[CONF_PRESET_MODE_COMMAND_TEMPLATE](
            preset_mode
        )
        await self._publish(
            CONF_PRESET_MODE_COMMAND_TOPIC,
            mqtt_payload,
        )

        if self._optimistic_preset_mode:
            self._attr_preset_mode = preset_mode
            self.async_write_ha_state()

    @override
    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if CONF_POWER_COMMAND_TOPIC in self._config:
            mqtt_payload = self._command_templates[CONF_POWER_COMMAND_TEMPLATE](
                self._config[CONF_PAYLOAD_ON]
            )
            await self._publish(CONF_POWER_COMMAND_TOPIC, mqtt_payload)
            return
        # Fall back to default behavior without power command topic
        await super().async_turn_on()

    @override
    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if CONF_POWER_COMMAND_TOPIC in self._config:
            mqtt_payload = self._command_templates[CONF_POWER_COMMAND_TEMPLATE](
                self._config[CONF_PAYLOAD_OFF]
            )
            await self._publish(CONF_POWER_COMMAND_TOPIC, mqtt_payload)
            if self._optimistic:
                self._attr_hvac_mode = HVACMode.OFF
                self.async_write_ha_state()
            return
        # Fall back to default behavior without power command topic
        await super().async_turn_off()
