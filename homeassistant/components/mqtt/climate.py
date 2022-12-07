"""Support for MQTT climate devices."""
from __future__ import annotations

from collections.abc import Callable
import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import climate
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
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
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_TEMPERATURE_UNIT,
    CONF_VALUE_TEMPLATE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import DEFAULT_RETAIN, MQTT_BASE_SCHEMA
from .const import CONF_ENCODING, CONF_QOS, CONF_RETAIN, PAYLOAD_NONE
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_setup_entry_helper,
    warn_for_legacy_schema,
)
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import get_mqtt_data, valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT HVAC"

CONF_ACTION_TEMPLATE = "action_template"
CONF_ACTION_TOPIC = "action_topic"
CONF_AUX_COMMAND_TOPIC = "aux_command_topic"
CONF_AUX_STATE_TEMPLATE = "aux_state_template"
CONF_AUX_STATE_TOPIC = "aux_state_topic"
# AWAY and HOLD mode topics and templates are no longer supported, support was removed with release 2022.9
CONF_AWAY_MODE_COMMAND_TOPIC = "away_mode_command_topic"
CONF_AWAY_MODE_STATE_TEMPLATE = "away_mode_state_template"
CONF_AWAY_MODE_STATE_TOPIC = "away_mode_state_topic"

CONF_CURRENT_TEMP_TEMPLATE = "current_temperature_template"
CONF_CURRENT_TEMP_TOPIC = "current_temperature_topic"
CONF_FAN_MODE_COMMAND_TEMPLATE = "fan_mode_command_template"
CONF_FAN_MODE_COMMAND_TOPIC = "fan_mode_command_topic"
CONF_FAN_MODE_LIST = "fan_modes"
CONF_FAN_MODE_STATE_TEMPLATE = "fan_mode_state_template"
CONF_FAN_MODE_STATE_TOPIC = "fan_mode_state_topic"
# AWAY and HOLD mode topics and templates are no longer supported, support was removed with release 2022.9
CONF_HOLD_COMMAND_TEMPLATE = "hold_command_template"
CONF_HOLD_COMMAND_TOPIC = "hold_command_topic"
CONF_HOLD_STATE_TEMPLATE = "hold_state_template"
CONF_HOLD_STATE_TOPIC = "hold_state_topic"
CONF_HOLD_LIST = "hold_modes"

CONF_MODE_COMMAND_TEMPLATE = "mode_command_template"
CONF_MODE_COMMAND_TOPIC = "mode_command_topic"
CONF_MODE_LIST = "modes"
CONF_MODE_STATE_TEMPLATE = "mode_state_template"
CONF_MODE_STATE_TOPIC = "mode_state_topic"
CONF_POWER_COMMAND_TOPIC = "power_command_topic"
CONF_POWER_STATE_TEMPLATE = "power_state_template"
CONF_POWER_STATE_TOPIC = "power_state_topic"
CONF_PRECISION = "precision"
CONF_PRESET_MODE_STATE_TOPIC = "preset_mode_state_topic"
CONF_PRESET_MODE_COMMAND_TOPIC = "preset_mode_command_topic"
CONF_PRESET_MODE_VALUE_TEMPLATE = "preset_mode_value_template"
CONF_PRESET_MODE_COMMAND_TEMPLATE = "preset_mode_command_template"
CONF_PRESET_MODES_LIST = "preset_modes"
# Support CONF_SEND_IF_OFF is removed with release 2022.9
CONF_SEND_IF_OFF = "send_if_off"
CONF_SWING_MODE_COMMAND_TEMPLATE = "swing_mode_command_template"
CONF_SWING_MODE_COMMAND_TOPIC = "swing_mode_command_topic"
CONF_SWING_MODE_LIST = "swing_modes"
CONF_SWING_MODE_STATE_TEMPLATE = "swing_mode_state_template"
CONF_SWING_MODE_STATE_TOPIC = "swing_mode_state_topic"
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

MQTT_CLIMATE_ATTRIBUTES_BLOCKED = frozenset(
    {
        climate.ATTR_AUX_HEAT,
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
    CONF_AUX_STATE_TEMPLATE,
    CONF_CURRENT_TEMP_TEMPLATE,
    CONF_FAN_MODE_STATE_TEMPLATE,
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
    CONF_MODE_COMMAND_TEMPLATE,
    CONF_PRESET_MODE_COMMAND_TEMPLATE,
    CONF_SWING_MODE_COMMAND_TEMPLATE,
    CONF_TEMP_COMMAND_TEMPLATE,
    CONF_TEMP_HIGH_COMMAND_TEMPLATE,
    CONF_TEMP_LOW_COMMAND_TEMPLATE,
}


TOPIC_KEYS = (
    CONF_ACTION_TOPIC,
    CONF_AUX_COMMAND_TOPIC,
    CONF_AUX_STATE_TOPIC,
    CONF_CURRENT_TEMP_TOPIC,
    CONF_FAN_MODE_COMMAND_TOPIC,
    CONF_FAN_MODE_STATE_TOPIC,
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
        raise ValueError("preset_modes must not include preset mode 'none'")
    return config


_PLATFORM_SCHEMA_BASE = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_AUX_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_AUX_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_AUX_STATE_TOPIC): valid_subscribe_topic,
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
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default="ON"): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default="OFF"): cv.string,
        vol.Optional(CONF_POWER_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_POWER_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_POWER_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_ACTION_TEMPLATE): cv.template,
        vol.Optional(CONF_ACTION_TOPIC): valid_subscribe_topic,
        # CONF_PRESET_MODE_COMMAND_TOPIC and CONF_PRESET_MODES_LIST must be used together
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
        vol.Optional(CONF_TEMP_INITIAL, default=21): cv.positive_int,
        vol.Optional(CONF_TEMP_MIN, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TEMP_MAX, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
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
    # Support CONF_SEND_IF_OFF is removed with release 2022.9
    cv.removed(CONF_SEND_IF_OFF),
    # AWAY and HOLD mode topics and templates are no longer supported, support was removed with release 2022.9
    cv.removed(CONF_AWAY_MODE_COMMAND_TOPIC),
    cv.removed(CONF_AWAY_MODE_STATE_TEMPLATE),
    cv.removed(CONF_AWAY_MODE_STATE_TOPIC),
    cv.removed(CONF_HOLD_COMMAND_TEMPLATE),
    cv.removed(CONF_HOLD_COMMAND_TOPIC),
    cv.removed(CONF_HOLD_STATE_TEMPLATE),
    cv.removed(CONF_HOLD_STATE_TOPIC),
    cv.removed(CONF_HOLD_LIST),
    _PLATFORM_SCHEMA_BASE,
    valid_preset_mode_configuration,
)

# Configuring MQTT Climate under the climate platform key was deprecated in HA Core 2022.6
# Setup for the legacy YAML format was removed in HA Core 2022.12
PLATFORM_SCHEMA = vol.All(
    warn_for_legacy_schema(climate.DOMAIN),
)

_DISCOVERY_SCHEMA_BASE = _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA)

DISCOVERY_SCHEMA = vol.All(
    _DISCOVERY_SCHEMA_BASE,
    # Support CONF_SEND_IF_OFF is removed with release 2022.9
    cv.removed(CONF_SEND_IF_OFF),
    # AWAY and HOLD mode topics and templates are no longer supported, support was removed with release 2022.9
    cv.removed(CONF_AWAY_MODE_COMMAND_TOPIC),
    cv.removed(CONF_AWAY_MODE_STATE_TEMPLATE),
    cv.removed(CONF_AWAY_MODE_STATE_TOPIC),
    cv.removed(CONF_HOLD_COMMAND_TEMPLATE),
    cv.removed(CONF_HOLD_COMMAND_TOPIC),
    cv.removed(CONF_HOLD_STATE_TEMPLATE),
    cv.removed(CONF_HOLD_STATE_TOPIC),
    cv.removed(CONF_HOLD_LIST),
    valid_preset_mode_configuration,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT climate device through configuration.yaml and dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, climate.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT climate devices."""
    async_add_entities([MqttClimate(hass, config, config_entry, discovery_data)])


class MqttClimate(MqttEntity, ClimateEntity):
    """Representation of an MQTT climate device."""

    _entity_id_format = climate.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_CLIMATE_ATTRIBUTES_BLOCKED

    _command_templates: dict[str, Callable[[PublishPayloadType], PublishPayloadType]]
    _value_templates: dict[str, Callable[[ReceivePayloadType], ReceivePayloadType]]
    _feature_preset_mode: bool
    _optimistic_preset_mode: bool
    _topic: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the climate device."""
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_hvac_modes = config[CONF_MODE_LIST]
        self._attr_min_temp = config[CONF_TEMP_MIN]
        self._attr_max_temp = config[CONF_TEMP_MAX]
        self._attr_precision = config.get(CONF_PRECISION, super().precision)
        self._attr_fan_modes = config[CONF_FAN_MODE_LIST]
        self._attr_swing_modes = config[CONF_SWING_MODE_LIST]
        self._attr_target_temperature_step = config[CONF_TEMP_STEP]
        self._attr_temperature_unit = config.get(
            CONF_TEMPERATURE_UNIT, self.hass.config.units.temperature_unit
        )

        self._topic = {key: config.get(key) for key in TOPIC_KEYS}

        # set to None in non-optimistic mode
        self._attr_target_temperature = None
        self._attr_fan_mode = None
        self._attr_hvac_mode = None
        self._attr_swing_mode = None
        self._attr_target_temperature_low = None
        self._attr_target_temperature_high = None

        if self._topic[CONF_TEMP_STATE_TOPIC] is None:
            self._attr_target_temperature = config[CONF_TEMP_INITIAL]
        if self._topic[CONF_TEMP_LOW_STATE_TOPIC] is None:
            self._attr_target_temperature_low = config[CONF_TEMP_INITIAL]
        if self._topic[CONF_TEMP_HIGH_STATE_TOPIC] is None:
            self._attr_target_temperature_high = config[CONF_TEMP_INITIAL]

        if self._topic[CONF_FAN_MODE_STATE_TOPIC] is None:
            self._attr_fan_mode = FAN_LOW
        if self._topic[CONF_SWING_MODE_STATE_TOPIC] is None:
            self._attr_swing_mode = SWING_OFF
        if self._topic[CONF_MODE_STATE_TOPIC] is None:
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
        self._optimistic_preset_mode = CONF_PRESET_MODE_STATE_TOPIC not in config
        self._attr_hvac_action = None

        self._attr_is_aux_heat = False

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

        support = ClimateEntityFeature(0)
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

        if (self._topic[CONF_AUX_STATE_TOPIC] is not None) or (
            self._topic[CONF_AUX_COMMAND_TOPIC] is not None
        ):
            support |= ClimateEntityFeature.AUX_HEAT
        self._attr_supported_features = support

    def _prepare_subscribe_topics(self) -> None:  # noqa: C901
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
        @log_messages(self.hass, self.entity_id)
        def handle_action_received(msg: ReceiveMessage) -> None:
            """Handle receiving action via MQTT."""
            payload = render_template(msg, CONF_ACTION_TEMPLATE)
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
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_subscription(topics, CONF_ACTION_TOPIC, handle_action_received)

        @callback
        def handle_temperature_received(
            msg: ReceiveMessage, template_name: str, attr: str
        ) -> None:
            """Handle temperature coming via MQTT."""
            payload = render_template(msg, template_name)

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
                msg, CONF_MODE_STATE_TEMPLATE, "_attr_hvac_mode", CONF_MODE_LIST
            )

        add_subscription(topics, CONF_MODE_STATE_TOPIC, handle_current_mode_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_fan_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving fan mode via MQTT."""
            handle_mode_received(
                msg,
                CONF_FAN_MODE_STATE_TEMPLATE,
                "_attr_fan_mode",
                CONF_FAN_MODE_LIST,
            )

        add_subscription(topics, CONF_FAN_MODE_STATE_TOPIC, handle_fan_mode_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_swing_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving swing mode via MQTT."""
            handle_mode_received(
                msg,
                CONF_SWING_MODE_STATE_TEMPLATE,
                "_attr_swing_mode",
                CONF_SWING_MODE_LIST,
            )

        add_subscription(
            topics, CONF_SWING_MODE_STATE_TOPIC, handle_swing_mode_received
        )

        @callback
        def handle_onoff_mode_received(
            msg: ReceiveMessage, template_name: str, attr: str
        ) -> None:
            """Handle receiving on/off mode via MQTT."""
            payload = render_template(msg, template_name)
            payload_on: str = self._config[CONF_PAYLOAD_ON]
            payload_off: str = self._config[CONF_PAYLOAD_OFF]

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
        def handle_aux_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving aux mode via MQTT."""
            handle_onoff_mode_received(
                msg, CONF_AUX_STATE_TEMPLATE, "_attr_is_aux_heat"
            )

        add_subscription(topics, CONF_AUX_STATE_TOPIC, handle_aux_mode_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_preset_mode_received(msg: ReceiveMessage) -> None:
            """Handle receiving preset mode via MQTT."""
            preset_mode = render_template(msg, CONF_PRESET_MODE_VALUE_TEMPLATE)
            if preset_mode in [PRESET_NONE, PAYLOAD_NONE]:
                self._attr_preset_mode = PRESET_NONE
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)
                return
            if not preset_mode:
                _LOGGER.debug("Ignoring empty preset_mode from '%s'", msg.topic)
                return
            if not self.preset_modes or preset_mode not in self.preset_modes:
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid preset mode",
                    msg.payload,
                    msg.topic,
                    preset_mode,
                )
            else:
                self._attr_preset_mode = str(preset_mode)

                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_subscription(
            topics, CONF_PRESET_MODE_STATE_TOPIC, handle_preset_mode_received
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

    async def _set_temperature(
        self,
        temp: float | None,
        cmnd_topic: str,
        cmnd_template: str,
        state_topic: str,
        attr: str,
    ) -> None:
        if temp is not None:
            if self._topic[state_topic] is None:
                # optimistic mode
                setattr(self, attr, temp)

            payload = self._command_templates[cmnd_template](temp)
            await self._publish(cmnd_topic, payload)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (operation_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(operation_mode)

        await self._set_temperature(
            kwargs.get(ATTR_TEMPERATURE),
            CONF_TEMP_COMMAND_TOPIC,
            CONF_TEMP_COMMAND_TEMPLATE,
            CONF_TEMP_STATE_TOPIC,
            "_attr_target_temperature",
        )

        await self._set_temperature(
            kwargs.get(ATTR_TARGET_TEMP_LOW),
            CONF_TEMP_LOW_COMMAND_TOPIC,
            CONF_TEMP_LOW_COMMAND_TEMPLATE,
            CONF_TEMP_LOW_STATE_TOPIC,
            "_attr_target_temperature_low",
        )

        await self._set_temperature(
            kwargs.get(ATTR_TARGET_TEMP_HIGH),
            CONF_TEMP_HIGH_COMMAND_TOPIC,
            CONF_TEMP_HIGH_COMMAND_TEMPLATE,
            CONF_TEMP_HIGH_STATE_TOPIC,
            "_attr_target_temperature_high",
        )

        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        payload = self._command_templates[CONF_SWING_MODE_COMMAND_TEMPLATE](swing_mode)
        await self._publish(CONF_SWING_MODE_COMMAND_TOPIC, payload)

        if self._topic[CONF_SWING_MODE_STATE_TOPIC] is None:
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target temperature."""
        payload = self._command_templates[CONF_FAN_MODE_COMMAND_TEMPLATE](fan_mode)
        await self._publish(CONF_FAN_MODE_COMMAND_TOPIC, payload)

        if self._topic[CONF_FAN_MODE_STATE_TOPIC] is None:
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if hvac_mode == HVACMode.OFF:
            await self._publish(
                CONF_POWER_COMMAND_TOPIC, self._config[CONF_PAYLOAD_OFF]
            )
        else:
            await self._publish(CONF_POWER_COMMAND_TOPIC, self._config[CONF_PAYLOAD_ON])

        payload = self._command_templates[CONF_MODE_COMMAND_TEMPLATE](hvac_mode)
        await self._publish(CONF_MODE_COMMAND_TOPIC, payload)

        if self._topic[CONF_MODE_STATE_TOPIC] is None:
            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a preset mode."""
        if self._feature_preset_mode and self.preset_modes:
            if preset_mode not in self.preset_modes and preset_mode is not PRESET_NONE:
                _LOGGER.warning("'%s' is not a valid preset mode", preset_mode)
                return
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

            return

    async def _set_aux_heat(self, state: bool) -> None:
        await self._publish(
            CONF_AUX_COMMAND_TOPIC,
            self._config[CONF_PAYLOAD_ON] if state else self._config[CONF_PAYLOAD_OFF],
        )

        if self._topic[CONF_AUX_STATE_TOPIC] is None:
            self._attr_is_aux_heat = state
            self.async_write_ha_state()

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        await self._set_aux_heat(True)

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        await self._set_aux_heat(False)
