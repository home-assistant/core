"""Support for MQTT climate devices."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol

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
    ClimateEntityFeature,
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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType
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

DEFAULT_NAME = "MQTT HVAC"

# Options CONF_AUX_COMMAND_TOPIC, CONF_AUX_STATE_TOPIC
# and CONF_AUX_STATE_TEMPLATE were deprecated in HA Core 2023.9
# Support was removed in HA Core 2024.3
CONF_AUX_COMMAND_TOPIC = "aux_command_topic"
CONF_AUX_STATE_TEMPLATE = "aux_state_template"
CONF_AUX_STATE_TOPIC = "aux_state_topic"

CONF_FAN_MODE_COMMAND_TEMPLATE = "fan_mode_command_template"
CONF_FAN_MODE_COMMAND_TOPIC = "fan_mode_command_topic"
CONF_FAN_MODE_LIST = "fan_modes"
CONF_FAN_MODE_STATE_TEMPLATE = "fan_mode_state_template"
CONF_FAN_MODE_STATE_TOPIC = "fan_mode_state_topic"

CONF_HUMIDITY_COMMAND_TEMPLATE = "target_humidity_command_template"
CONF_HUMIDITY_COMMAND_TOPIC = "target_humidity_command_topic"
CONF_HUMIDITY_STATE_TEMPLATE = "target_humidity_state_template"
CONF_HUMIDITY_STATE_TOPIC = "target_humidity_state_topic"
CONF_HUMIDITY_MAX = "max_humidity"
CONF_HUMIDITY_MIN = "min_humidity"

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

DEFAULT_INITIAL_TEMPERATURE = 21.0

MQTT_CLIMATE_ATTRIBUTES_BLOCKED = frozenset(
    {
        climate.ATTR_CURRENT_HUMIDITY,
        climate.ATTR_CURRENT_TEMPERATURE,
        climate.ATTR_FAN_MODE,
        climate.ATTR_FAN_MODES,
        climate.ATTR_HUMIDITY,
        climate.ATTR_HVAC_ACTION,
        climate.ATTR_HVAC_MODES,
        climate.ATTR_MAX_HUMIDITY,
        climate.ATTR_MAX_TEMP,
        climate.ATTR_MIN_HUMIDITY,
        climate.ATTR_MIN_TEMP,
        climate.ATTR_PRESET_MODE,
        climate.ATTR_PRESET_MODES,
        climate.ATTR_SWING_MODE,
        climate.ATTR_SWING_MODES,
        climate.ATTR_TARGET_TEMP_HIGH,
        climate.ATTR_TARGET_TEMP_LOW,
        climate.ATTR_TARGET_TEMP_STEP,
        climate.ATTR_TEMPERATURE,
    }
)

VALUE_TEMPLATE_KEYS = (
    CONF_CURRENT_HUMIDITY_TEMPLATE,
    CONF_CURRENT_TEMP_TEMPLATE,
    CONF_FAN_MODE_STATE_TEMPLATE,
    CONF_HUMIDITY_STATE_TEMPLATE,
    CONF_MODE_STATE_TEMPLATE,
    CONF_POWER_STATE_TEMPLATE,
    CONF_ACTION_TEMPLATE,
    CONF_PRESET_MODE_VALUE_TEMPLATE,
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
    CONF_POWER_STATE_TOPIC,
    CONF_PRESET_MODE_COMMAND_TOPIC,
    CONF_PRESET_MODE_STATE_TOPIC,
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
        raise vol.Invalid("preset_modes must not include preset mode 'none'")
    return config


def valid_humidity_range_configuration(config: ConfigType) -> ConfigType:
    """Validate a target_humidity range configuration, throws otherwise."""
    if config[CONF_HUMIDITY_MIN] >= config[CONF_HUMIDITY_MAX]:
        raise vol.Invalid("target_humidity_max must be > target_humidity_min")
    if config[CONF_HUMIDITY_MAX] > 100:
        raise vol.Invalid("max_humidity must be <= 100")

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
        raise vol.Invalid(
            f"{CONF_HUMIDITY_STATE_TOPIC} cannot be used without"
            f" {CONF_HUMIDITY_COMMAND_TOPIC}"
        )

    return config


_PLATFORM_SCHEMA_BASE = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_CURRENT_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_HUMIDITY_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_CURRENT_TEMP_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_TEMP_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_FAN_MODE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_FAN_MODE_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(
            CONF_FAN_MODE_LIST,
            default=[FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
        ): cv.ensure_list,
        vol.Optional(CONF_FAN_MODE_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_FAN_MODE_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_HUMIDITY_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_HUMIDITY_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_HUMIDITY_MIN, default=DEFAULT_MIN_HUMIDITY): vol.Coerce(
            float
        ),
        vol.Optional(CONF_HUMIDITY_MAX, default=DEFAULT_MAX_HUMIDITY): vol.Coerce(
            float
        ),
        vol.Optional(CONF_HUMIDITY_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_HUMIDITY_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_MODE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_MODE_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(
            CONF_MODE_LIST,
            default=[
                HVACMode.AUTO,
                HVACMode.OFF,
                HVACMode.COOL,
                HVACMode.HEAT,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
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
        vol.Optional(CONF_POWER_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_POWER_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_ACTION_TEMPLATE): cv.template,
        vol.Optional(CONF_ACTION_TOPIC): valid_subscribe_topic,
        # CONF_PRESET_MODE_COMMAND_TOPIC and CONF_PRESET_MODES_LIST
        # must be used together
        vol.Inclusive(
            CONF_PRESET_MODE_COMMAND_TOPIC, "preset_modes"
        ): valid_publish_topic,
        vol.Inclusive(
            CONF_PRESET_MODES_LIST, "preset_modes", default=[]
        ): cv.ensure_list,
        vol.Optional(CONF_PRESET_MODE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_PRESET_MODE_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_PRESET_MODE_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_SWING_MODE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_SWING_MODE_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(
            CONF_SWING_MODE_LIST, default=[SWING_ON, SWING_OFF]
        ): cv.ensure_list,
        vol.Optional(CONF_SWING_MODE_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_SWING_MODE_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_TEMP_INITIAL): vol.All(vol.Coerce(float)),
        vol.Optional(CONF_TEMP_MIN): vol.Coerce(float),
        vol.Optional(CONF_TEMP_MAX): vol.Coerce(float),
        vol.Optional(CONF_TEMP_STEP, default=1.0): vol.Coerce(float),
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

PLATFORM_SCHEMA_MODERN = vol.All(
    # Support for CONF_POWER_STATE_TOPIC and CONF_POWER_STATE_TEMPLATE
    # was removed in HA Core 2023.8
    cv.removed(CONF_POWER_STATE_TEMPLATE),
    cv.removed(CONF_POWER_STATE_TOPIC),
    # Options CONF_AUX_COMMAND_TOPIC, CONF_AUX_STATE_TOPIC
    # and CONF_AUX_STATE_TEMPLATE were deprecated in HA Core 2023.9
    # Support was removed in HA Core 2024.3
    cv.removed(CONF_AUX_COMMAND_TOPIC),
    cv.removed(CONF_AUX_STATE_TEMPLATE),
    cv.removed(CONF_AUX_STATE_TOPIC),
    _PLATFORM_SCHEMA_BASE,
    valid_preset_mode_configuration,
    valid_humidity_range_configuration,
    valid_humidity_state_configuration,
)

_DISCOVERY_SCHEMA_BASE = _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA)

DISCOVERY_SCHEMA = vol.All(
    _DISCOVERY_SCHEMA_BASE,
    # Support for CONF_POWER_STATE_TOPIC and CONF_POWER_STATE_TEMPLATE
    # was removed in HA Core 2023.8
    cv.removed(CONF_POWER_STATE_TEMPLATE),
    cv.removed(CONF_POWER_STATE_TOPIC),
    valid_preset_mode_configuration,
    valid_humidity_range_configuration,
    valid_humidity_state_configuration,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT climate through YAML and through MQTT discovery."""
    await async_setup_entity_entry_helper(
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

    _attr_target_temperature_low: float | None
    _attr_target_temperature_high: float | None

    _feature_preset_mode: bool = False
    _optimistic: bool
    _topic: dict[str, Any]

    _command_templates: dict[str, Callable[[PublishPayloadType], PublishPayloadType]]
    _value_templates: dict[str, Callable[[ReceivePayloadType], ReceivePayloadType]]

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
        if self._topic[topic] is not None:
            await self.async_publish(
                self._topic[topic],
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

    @abstractmethod
    async def async_set_temperature(self, **kwargs: Any) -> None:
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


class MqttClimate(MqttTemperatureControlEntity, ClimateEntity):
    """Representation of an MQTT climate device."""

    _attr_fan_mode: str | None = None
    _attr_hvac_mode: HVACMode | None = None
    _attr_swing_mode: str | None = None
    _default_name = DEFAULT_NAME
    _entity_id_format = climate.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_CLIMATE_ATTRIBUTES_BLOCKED
    _attr_target_temperature_low: float | None = None
    _attr_target_temperature_high: float | None = None
    _enable_turn_on_off_backwards_compatibility = False

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_hvac_modes = config[CONF_MODE_LIST]
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
        self._attr_swing_modes = config[CONF_SWING_MODE_LIST]
        self._attr_target_temperature_step = config[CONF_TEMP_STEP]

        self._topic = {key: config.get(key) for key in TOPIC_KEYS}

        self._optimistic = config[CONF_OPTIMISTIC]

        # Set init temp, if it is missing convert the default to the temperature units
        init_temp: float = config.get(
            CONF_TEMP_INITIAL,
            TemperatureConverter.convert(
                DEFAULT_INITIAL_TEMPERATURE,
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

        if (self._topic[CONF_SWING_MODE_STATE_TOPIC] is not None) or (
            self._topic[CONF_SWING_MODE_COMMAND_TOPIC] is not None
        ):
            support |= ClimateEntityFeature.SWING_MODE

        if self._feature_preset_mode:
            support |= ClimateEntityFeature.PRESET_MODE

        self._attr_supported_features = support

    def _prepare_subscribe_topics(self) -> None:  # noqa: C901
        """(Re)Subscribe to topics."""
        topics: dict[str, dict[str, Any]] = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_hvac_action"})
        def handle_action_received(msg: ReceiveMessage) -> None:
            """Handle receiving action via MQTT."""
            payload = self.render_template(msg, CONF_ACTION_TEMPLATE)
            if not payload or payload == PAYLOAD_NONE:
                _LOGGER.debug(
                    "Invalid %s action: %s, ignoring",
                    [e.value for e in HVACAction],
                    payload,
                )
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

        self.add_subscription(topics, CONF_ACTION_TOPIC, handle_action_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_current_humidity"})
        def handle_current_humidity_received(msg: ReceiveMessage) -> None:
            """Handle current humidity coming via MQTT."""
            self.handle_climate_attribute_received(
                msg, CONF_CURRENT_HUMIDITY_TEMPLATE, "_attr_current_humidity"
            )

        self.add_subscription(
            topics, CONF_CURRENT_HUMIDITY_TOPIC, handle_current_humidity_received
        )

        @callback
        @write_state_on_attr_change(self, {"_attr_target_humidity"})
        @log_messages(self.hass, self.entity_id)
        def handle_target_humidity_received(msg: ReceiveMessage) -> None:
            """Handle target humidity coming via MQTT."""

            self.handle_climate_attribute_received(
                msg, CONF_HUMIDITY_STATE_TEMPLATE, "_attr_target_humidity"
            )

        self.add_subscription(
            topics, CONF_HUMIDITY_STATE_TOPIC, handle_target_humidity_received
        )

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
        @write_state_on_attr_change(self, {"_attr_hvac_mode"})
        def handle_current_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving mode via MQTT."""
            handle_mode_received(
                msg, CONF_MODE_STATE_TEMPLATE, "_attr_hvac_mode", CONF_MODE_LIST
            )

        self.add_subscription(
            topics, CONF_MODE_STATE_TOPIC, handle_current_mode_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_fan_mode"})
        def handle_fan_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving fan mode via MQTT."""
            handle_mode_received(
                msg,
                CONF_FAN_MODE_STATE_TEMPLATE,
                "_attr_fan_mode",
                CONF_FAN_MODE_LIST,
            )

        self.add_subscription(
            topics, CONF_FAN_MODE_STATE_TOPIC, handle_fan_mode_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_swing_mode"})
        def handle_swing_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving swing mode via MQTT."""
            handle_mode_received(
                msg,
                CONF_SWING_MODE_STATE_TEMPLATE,
                "_attr_swing_mode",
                CONF_SWING_MODE_LIST,
            )

        self.add_subscription(
            topics, CONF_SWING_MODE_STATE_TOPIC, handle_swing_mode_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_preset_mode"})
        def handle_preset_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving preset mode via MQTT."""
            preset_mode = self.render_template(msg, CONF_PRESET_MODE_VALUE_TEMPLATE)
            if preset_mode in [PRESET_NONE, PAYLOAD_NONE]:
                self._attr_preset_mode = PRESET_NONE
                return
            if not preset_mode:
                _LOGGER.debug("Ignoring empty preset_mode from '%s'", msg.topic)
                return
            if (
                not self._attr_preset_modes
                or preset_mode not in self._attr_preset_modes
            ):
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid preset mode",
                    msg.payload,
                    msg.topic,
                    preset_mode,
                )
            else:
                self._attr_preset_mode = str(preset_mode)

        self.add_subscription(
            topics, CONF_PRESET_MODE_STATE_TOPIC, handle_preset_mode_received
        )

        self.prepare_subscribe_topics(topics)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        operation_mode: HVACMode | None
        if (operation_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(operation_mode)
        await super().async_set_temperature(**kwargs)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""

        await self._set_climate_attribute(
            humidity,
            CONF_HUMIDITY_COMMAND_TOPIC,
            CONF_HUMIDITY_COMMAND_TEMPLATE,
            CONF_HUMIDITY_STATE_TOPIC,
            "_attr_target_humidity",
        )

        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        payload = self._command_templates[CONF_SWING_MODE_COMMAND_TEMPLATE](swing_mode)
        await self._publish(CONF_SWING_MODE_COMMAND_TOPIC, payload)

        if self._optimistic or self._topic[CONF_SWING_MODE_STATE_TOPIC] is None:
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target temperature."""
        payload = self._command_templates[CONF_FAN_MODE_COMMAND_TEMPLATE](fan_mode)
        await self._publish(CONF_FAN_MODE_COMMAND_TOPIC, payload)

        if self._optimistic or self._topic[CONF_FAN_MODE_STATE_TOPIC] is None:
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        payload = self._command_templates[CONF_MODE_COMMAND_TEMPLATE](hvac_mode)
        await self._publish(CONF_MODE_COMMAND_TOPIC, payload)

        if self._optimistic or self._topic[CONF_MODE_STATE_TOPIC] is None:
            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()

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
