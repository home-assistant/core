"""Support for MQTT fans."""
from __future__ import annotations

import functools
import logging
import math
from typing import Any

import voluptuous as vol

from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_STATE,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_STATE_VALUE_TEMPLATE,
    PAYLOAD_NONE,
)
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_discover_yaml_entities,
    async_setup_entry_helper,
    async_setup_platform_helper,
    warn_for_legacy_schema,
)
from .models import MqttCommandTemplate, MqttValueTemplate
from .util import valid_publish_topic, valid_subscribe_topic

CONF_PERCENTAGE_STATE_TOPIC = "percentage_state_topic"
CONF_PERCENTAGE_COMMAND_TOPIC = "percentage_command_topic"
CONF_PERCENTAGE_VALUE_TEMPLATE = "percentage_value_template"
CONF_PERCENTAGE_COMMAND_TEMPLATE = "percentage_command_template"
CONF_PAYLOAD_RESET_PERCENTAGE = "payload_reset_percentage"
CONF_SPEED_RANGE_MIN = "speed_range_min"
CONF_SPEED_RANGE_MAX = "speed_range_max"
CONF_PRESET_MODE_STATE_TOPIC = "preset_mode_state_topic"
CONF_PRESET_MODE_COMMAND_TOPIC = "preset_mode_command_topic"
CONF_PRESET_MODE_VALUE_TEMPLATE = "preset_mode_value_template"
CONF_PRESET_MODE_COMMAND_TEMPLATE = "preset_mode_command_template"
CONF_PRESET_MODES_LIST = "preset_modes"
CONF_PAYLOAD_RESET_PRESET_MODE = "payload_reset_preset_mode"
CONF_SPEED_STATE_TOPIC = "speed_state_topic"
CONF_SPEED_COMMAND_TOPIC = "speed_command_topic"
CONF_SPEED_VALUE_TEMPLATE = "speed_value_template"
CONF_OSCILLATION_STATE_TOPIC = "oscillation_state_topic"
CONF_OSCILLATION_COMMAND_TOPIC = "oscillation_command_topic"
CONF_OSCILLATION_VALUE_TEMPLATE = "oscillation_value_template"
CONF_OSCILLATION_COMMAND_TEMPLATE = "oscillation_command_template"
CONF_PAYLOAD_OSCILLATION_ON = "payload_oscillation_on"
CONF_PAYLOAD_OSCILLATION_OFF = "payload_oscillation_off"
CONF_PAYLOAD_OFF_SPEED = "payload_off_speed"
CONF_PAYLOAD_LOW_SPEED = "payload_low_speed"
CONF_PAYLOAD_MEDIUM_SPEED = "payload_medium_speed"
CONF_PAYLOAD_HIGH_SPEED = "payload_high_speed"
CONF_SPEED_LIST = "speeds"

DEFAULT_NAME = "MQTT Fan"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_PAYLOAD_RESET = "None"
DEFAULT_OPTIMISTIC = False
DEFAULT_SPEED_RANGE_MIN = 1
DEFAULT_SPEED_RANGE_MAX = 100

OSCILLATE_ON_PAYLOAD = "oscillate_on"
OSCILLATE_OFF_PAYLOAD = "oscillate_off"

MQTT_FAN_ATTRIBUTES_BLOCKED = frozenset(
    {
        fan.ATTR_DIRECTION,
        fan.ATTR_OSCILLATING,
        fan.ATTR_PERCENTAGE_STEP,
        fan.ATTR_PERCENTAGE,
        fan.ATTR_PRESET_MODE,
        fan.ATTR_PRESET_MODES,
    }
)

_LOGGER = logging.getLogger(__name__)


def valid_speed_range_configuration(config):
    """Validate that the fan speed_range configuration is valid, throws if it isn't."""
    if config.get(CONF_SPEED_RANGE_MIN) == 0:
        raise ValueError("speed_range_min must be > 0")
    if config.get(CONF_SPEED_RANGE_MIN) >= config.get(CONF_SPEED_RANGE_MAX):
        raise ValueError("speed_range_max must be > speed_range_min")
    return config


def valid_preset_mode_configuration(config):
    """Validate that the preset mode reset payload is not one of the preset modes."""
    if config.get(CONF_PAYLOAD_RESET_PRESET_MODE) in config.get(CONF_PRESET_MODES_LIST):
        raise ValueError("preset_modes must not contain payload_reset_preset_mode")
    return config


_PLATFORM_SCHEMA_BASE = MQTT_RW_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_OSCILLATION_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_OSCILLATION_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_OSCILLATION_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_OSCILLATION_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_PERCENTAGE_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_PERCENTAGE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_PERCENTAGE_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_PERCENTAGE_VALUE_TEMPLATE): cv.template,
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
        vol.Optional(
            CONF_SPEED_RANGE_MIN, default=DEFAULT_SPEED_RANGE_MIN
        ): cv.positive_int,
        vol.Optional(
            CONF_SPEED_RANGE_MAX, default=DEFAULT_SPEED_RANGE_MAX
        ): cv.positive_int,
        vol.Optional(
            CONF_PAYLOAD_RESET_PERCENTAGE, default=DEFAULT_PAYLOAD_RESET
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_RESET_PRESET_MODE, default=DEFAULT_PAYLOAD_RESET
        ): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(
            CONF_PAYLOAD_OSCILLATION_OFF, default=OSCILLATE_OFF_PAYLOAD
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_OSCILLATION_ON, default=OSCILLATE_ON_PAYLOAD
        ): cv.string,
        vol.Optional(CONF_SPEED_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_SPEED_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_SPEED_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

# Configuring MQTT Fans under the fan platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    cv.PLATFORM_SCHEMA.extend(_PLATFORM_SCHEMA_BASE.schema),
    valid_speed_range_configuration,
    valid_preset_mode_configuration,
    warn_for_legacy_schema(fan.DOMAIN),
)

PLATFORM_SCHEMA_MODERN = vol.All(
    # CONF_SPEED_COMMAND_TOPIC, CONF_SPEED_LIST, CONF_SPEED_STATE_TOPIC, CONF_SPEED_VALUE_TEMPLATE and
    # Speeds SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH SPEED_OFF,
    # are no longer supported, support was removed in release 2021.12
    cv.removed(CONF_PAYLOAD_HIGH_SPEED),
    cv.removed(CONF_PAYLOAD_LOW_SPEED),
    cv.removed(CONF_PAYLOAD_MEDIUM_SPEED),
    cv.removed(CONF_SPEED_COMMAND_TOPIC),
    cv.removed(CONF_SPEED_LIST),
    cv.removed(CONF_SPEED_STATE_TOPIC),
    cv.removed(CONF_SPEED_VALUE_TEMPLATE),
    _PLATFORM_SCHEMA_BASE,
    valid_speed_range_configuration,
    valid_preset_mode_configuration,
)

DISCOVERY_SCHEMA = vol.All(
    # CONF_SPEED_COMMAND_TOPIC, CONF_SPEED_LIST, CONF_SPEED_STATE_TOPIC, CONF_SPEED_VALUE_TEMPLATE and
    # Speeds SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH SPEED_OFF,
    # are no longer supported, support was removed in release 2021.12
    cv.removed(CONF_PAYLOAD_HIGH_SPEED),
    cv.removed(CONF_PAYLOAD_LOW_SPEED),
    cv.removed(CONF_PAYLOAD_MEDIUM_SPEED),
    cv.removed(CONF_SPEED_COMMAND_TOPIC),
    cv.removed(CONF_SPEED_LIST),
    cv.removed(CONF_SPEED_STATE_TOPIC),
    cv.removed(CONF_SPEED_VALUE_TEMPLATE),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
    valid_speed_range_configuration,
    valid_preset_mode_configuration,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT fans configured under the fan platform key (deprecated)."""
    # Deprecated in HA Core 2022.6
    await async_setup_platform_helper(
        hass,
        fan.DOMAIN,
        discovery_info or config,
        async_add_entities,
        _async_setup_entity,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT fan through configuration.yaml and dynamically through MQTT discovery."""
    # load and initialize platform config from configuration.yaml
    await async_discover_yaml_entities(hass, fan.DOMAIN)
    # setup for discovery
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, fan.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry | None = None,
    discovery_data: dict | None = None,
) -> None:
    """Set up the MQTT fan."""
    async_add_entities([MqttFan(hass, config, config_entry, discovery_data)])


class MqttFan(MqttEntity, FanEntity):
    """A MQTT fan component."""

    _entity_id_format = fan.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_FAN_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT fan."""
        self._state = None
        self._percentage = None
        self._preset_mode = None
        self._oscillation = None
        self._supported_features = 0

        self._topic = None
        self._payload = None
        self._value_templates = None
        self._command_templates = None
        self._optimistic = None
        self._optimistic_oscillation = None
        self._optimistic_percentage = None
        self._optimistic_preset_mode = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._speed_range = (
            config.get(CONF_SPEED_RANGE_MIN),
            config.get(CONF_SPEED_RANGE_MAX),
        )
        self._topic = {
            key: config.get(key)
            for key in (
                CONF_STATE_TOPIC,
                CONF_COMMAND_TOPIC,
                CONF_PERCENTAGE_STATE_TOPIC,
                CONF_PERCENTAGE_COMMAND_TOPIC,
                CONF_PRESET_MODE_STATE_TOPIC,
                CONF_PRESET_MODE_COMMAND_TOPIC,
                CONF_OSCILLATION_STATE_TOPIC,
                CONF_OSCILLATION_COMMAND_TOPIC,
            )
        }
        self._value_templates = {
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
            ATTR_PERCENTAGE: config.get(CONF_PERCENTAGE_VALUE_TEMPLATE),
            ATTR_PRESET_MODE: config.get(CONF_PRESET_MODE_VALUE_TEMPLATE),
            ATTR_OSCILLATING: config.get(CONF_OSCILLATION_VALUE_TEMPLATE),
        }
        self._command_templates = {
            CONF_STATE: config.get(CONF_COMMAND_TEMPLATE),
            ATTR_PERCENTAGE: config.get(CONF_PERCENTAGE_COMMAND_TEMPLATE),
            ATTR_PRESET_MODE: config.get(CONF_PRESET_MODE_COMMAND_TEMPLATE),
            ATTR_OSCILLATING: config.get(CONF_OSCILLATION_COMMAND_TEMPLATE),
        }
        self._payload = {
            "STATE_ON": config[CONF_PAYLOAD_ON],
            "STATE_OFF": config[CONF_PAYLOAD_OFF],
            "OSCILLATE_ON_PAYLOAD": config[CONF_PAYLOAD_OSCILLATION_ON],
            "OSCILLATE_OFF_PAYLOAD": config[CONF_PAYLOAD_OSCILLATION_OFF],
            "PERCENTAGE_RESET": config[CONF_PAYLOAD_RESET_PERCENTAGE],
            "PRESET_MODE_RESET": config[CONF_PAYLOAD_RESET_PRESET_MODE],
        }

        self._feature_percentage = CONF_PERCENTAGE_COMMAND_TOPIC in config
        self._feature_preset_mode = CONF_PRESET_MODE_COMMAND_TOPIC in config
        if self._feature_preset_mode:
            self._preset_modes = config[CONF_PRESET_MODES_LIST]
        else:
            self._preset_modes = []

        self._speed_count = (
            min(int_states_in_range(self._speed_range), 100)
            if self._feature_percentage
            else 100
        )

        optimistic = config[CONF_OPTIMISTIC]
        self._optimistic = optimistic or self._topic[CONF_STATE_TOPIC] is None
        self._optimistic_oscillation = (
            optimistic or self._topic[CONF_OSCILLATION_STATE_TOPIC] is None
        )
        self._optimistic_percentage = (
            optimistic or self._topic[CONF_PERCENTAGE_STATE_TOPIC] is None
        )
        self._optimistic_preset_mode = (
            optimistic or self._topic[CONF_PRESET_MODE_STATE_TOPIC] is None
        )

        self._supported_features = 0
        self._supported_features |= (
            self._topic[CONF_OSCILLATION_COMMAND_TOPIC] is not None
            and FanEntityFeature.OSCILLATE
        )
        if self._feature_percentage:
            self._supported_features |= FanEntityFeature.SET_SPEED
        if self._feature_preset_mode:
            self._supported_features |= FanEntityFeature.PRESET_MODE

        for key, tpl in self._command_templates.items():
            self._command_templates[key] = MqttCommandTemplate(
                tpl, entity=self
            ).async_render

        for key, tpl in self._value_templates.items():
            self._value_templates[key] = MqttValueTemplate(
                tpl,
                entity=self,
            ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg):
            """Handle new received MQTT message."""
            payload = self._value_templates[CONF_STATE](msg.payload)
            if not payload:
                _LOGGER.debug("Ignoring empty state from '%s'", msg.topic)
                return
            if payload == self._payload["STATE_ON"]:
                self._state = True
            elif payload == self._payload["STATE_OFF"]:
                self._state = False
            elif payload == PAYLOAD_NONE:
                self._state = None
            self.async_write_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            topics[CONF_STATE_TOPIC] = {
                "topic": self._topic[CONF_STATE_TOPIC],
                "msg_callback": state_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }

        @callback
        @log_messages(self.hass, self.entity_id)
        def percentage_received(msg):
            """Handle new received MQTT message for the percentage."""
            rendered_percentage_payload = self._value_templates[ATTR_PERCENTAGE](
                msg.payload
            )
            if not rendered_percentage_payload:
                _LOGGER.debug("Ignoring empty speed from '%s'", msg.topic)
                return
            if rendered_percentage_payload == self._payload["PERCENTAGE_RESET"]:
                self._percentage = None
                self.async_write_ha_state()
                return
            try:
                percentage = ranged_value_to_percentage(
                    self._speed_range, int(rendered_percentage_payload)
                )
            except ValueError:
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid speed within the speed range",
                    msg.payload,
                    msg.topic,
                    rendered_percentage_payload,
                )
                return
            if percentage < 0 or percentage > 100:
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid speed within the speed range",
                    msg.payload,
                    msg.topic,
                    rendered_percentage_payload,
                )
                return
            self._percentage = percentage
            self.async_write_ha_state()

        if self._topic[CONF_PERCENTAGE_STATE_TOPIC] is not None:
            topics[CONF_PERCENTAGE_STATE_TOPIC] = {
                "topic": self._topic[CONF_PERCENTAGE_STATE_TOPIC],
                "msg_callback": percentage_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }
            self._percentage = None

        @callback
        @log_messages(self.hass, self.entity_id)
        def preset_mode_received(msg):
            """Handle new received MQTT message for preset mode."""
            preset_mode = self._value_templates[ATTR_PRESET_MODE](msg.payload)
            if preset_mode == self._payload["PRESET_MODE_RESET"]:
                self._preset_mode = None
                self.async_write_ha_state()
                return
            if not preset_mode:
                _LOGGER.debug("Ignoring empty preset_mode from '%s'", msg.topic)
                return
            if preset_mode not in self.preset_modes:
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid preset mode",
                    msg.payload,
                    msg.topic,
                    preset_mode,
                )
                return

            self._preset_mode = preset_mode
            self.async_write_ha_state()

        if self._topic[CONF_PRESET_MODE_STATE_TOPIC] is not None:
            topics[CONF_PRESET_MODE_STATE_TOPIC] = {
                "topic": self._topic[CONF_PRESET_MODE_STATE_TOPIC],
                "msg_callback": preset_mode_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }
            self._preset_mode = None

        @callback
        @log_messages(self.hass, self.entity_id)
        def oscillation_received(msg):
            """Handle new received MQTT message for the oscillation."""
            payload = self._value_templates[ATTR_OSCILLATING](msg.payload)
            if not payload:
                _LOGGER.debug("Ignoring empty oscillation from '%s'", msg.topic)
                return
            if payload == self._payload["OSCILLATE_ON_PAYLOAD"]:
                self._oscillation = True
            elif payload == self._payload["OSCILLATE_OFF_PAYLOAD"]:
                self._oscillation = False
            self.async_write_ha_state()

        if self._topic[CONF_OSCILLATION_STATE_TOPIC] is not None:
            topics[CONF_OSCILLATION_STATE_TOPIC] = {
                "topic": self._topic[CONF_OSCILLATION_STATE_TOPIC],
                "msg_callback": oscillation_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }
            self._oscillation = False

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._state

    @property
    def percentage(self) -> int | None:
        """Return the current percentage."""
        return self._percentage

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset _mode."""
        return self._preset_mode

    @property
    def preset_modes(self) -> list[str]:
        """Get the list of available preset modes."""
        return self._preset_modes

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._speed_count

    @property
    def oscillating(self) -> bool | None:
        """Return the oscillation state."""
        return self._oscillation

    # The speed attribute deprecated in the schema, support will be removed after a quarter (2021.7)
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the entity.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[CONF_STATE](self._payload["STATE_ON"])
        await self.async_publish(
            self._topic[CONF_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if percentage:
            await self.async_set_percentage(percentage)
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        if self._optimistic:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[CONF_STATE](self._payload["STATE_OFF"])
        await self.async_publish(
            self._topic[CONF_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            self._state = False
            self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan.

        This method is a coroutine.
        """
        percentage_payload = math.ceil(
            percentage_to_ranged_value(self._speed_range, percentage)
        )
        mqtt_payload = self._command_templates[ATTR_PERCENTAGE](percentage_payload)
        await self.async_publish(
            self._topic[CONF_PERCENTAGE_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        if self._optimistic_percentage:
            self._percentage = percentage
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan.

        This method is a coroutine.
        """
        self._valid_preset_mode_or_raise(preset_mode)

        mqtt_payload = self._command_templates[ATTR_PRESET_MODE](preset_mode)

        await self.async_publish(
            self._topic[CONF_PRESET_MODE_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        if self._optimistic_preset_mode:
            self._preset_mode = preset_mode
            self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation.

        This method is a coroutine.
        """
        if oscillating:
            mqtt_payload = self._command_templates[ATTR_OSCILLATING](
                self._payload["OSCILLATE_ON_PAYLOAD"]
            )
        else:
            mqtt_payload = self._command_templates[ATTR_OSCILLATING](
                self._payload["OSCILLATE_OFF_PAYLOAD"]
            )

        await self.async_publish(
            self._topic[CONF_OSCILLATION_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        if self._optimistic_oscillation:
            self._oscillation = oscillating
            self.async_write_ha_state()
