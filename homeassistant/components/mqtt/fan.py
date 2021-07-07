"""Support for MQTT fans."""
import functools
import logging
import math

import voluptuous as vol

from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_SPEED,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_OSCILLATE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
    speed_list_without_preset_modes,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_STATE,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.percentage import (
    int_states_in_range,
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import (
    CONF_COMMAND_TOPIC,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    DOMAIN,
    PLATFORMS,
    subscription,
)
from .. import mqtt
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper

CONF_STATE_VALUE_TEMPLATE = "state_value_template"
CONF_COMMAND_TEMPLATE = "command_template"
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
        fan.ATTR_SPEED_LIST,
        fan.ATTR_SPEED,
    }
)

_LOGGER = logging.getLogger(__name__)


def valid_fan_speed_configuration(config):
    """Validate that the fan speed configuration is valid, throws if it isn't."""
    if config.get(CONF_SPEED_COMMAND_TOPIC) and not speed_list_without_preset_modes(
        config.get(CONF_SPEED_LIST)
    ):
        raise ValueError("No valid speeds configured")
    return config


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


PLATFORM_SCHEMA = vol.All(
    # CONF_SPEED_COMMAND_TOPIC, CONF_SPEED_LIST, CONF_SPEED_STATE_TOPIC, CONF_SPEED_VALUE_TEMPLATE and
    # Speeds SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH SPEED_OFF,
    # are deprecated, support will be removed after a quarter (2021.7)
    cv.deprecated(CONF_PAYLOAD_HIGH_SPEED),
    cv.deprecated(CONF_PAYLOAD_LOW_SPEED),
    cv.deprecated(CONF_PAYLOAD_MEDIUM_SPEED),
    cv.deprecated(CONF_SPEED_COMMAND_TOPIC),
    cv.deprecated(CONF_SPEED_LIST),
    cv.deprecated(CONF_SPEED_STATE_TOPIC),
    cv.deprecated(CONF_SPEED_VALUE_TEMPLATE),
    mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_OSCILLATION_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_OSCILLATION_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_OSCILLATION_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_OSCILLATION_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_PERCENTAGE_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_PERCENTAGE_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_PERCENTAGE_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_PERCENTAGE_VALUE_TEMPLATE): cv.template,
            # CONF_PRESET_MODE_COMMAND_TOPIC and CONF_PRESET_MODES_LIST must be used together
            vol.Inclusive(
                CONF_PRESET_MODE_COMMAND_TOPIC, "preset_modes"
            ): mqtt.valid_publish_topic,
            vol.Inclusive(
                CONF_PRESET_MODES_LIST, "preset_modes", default=[]
            ): cv.ensure_list,
            vol.Optional(CONF_PRESET_MODE_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_PRESET_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
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
            vol.Optional(CONF_PAYLOAD_HIGH_SPEED, default=SPEED_HIGH): cv.string,
            vol.Optional(CONF_PAYLOAD_LOW_SPEED, default=SPEED_LOW): cv.string,
            vol.Optional(CONF_PAYLOAD_MEDIUM_SPEED, default=SPEED_MEDIUM): cv.string,
            vol.Optional(CONF_PAYLOAD_OFF_SPEED, default=SPEED_OFF): cv.string,
            vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
            vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
            vol.Optional(
                CONF_PAYLOAD_OSCILLATION_OFF, default=OSCILLATE_OFF_PAYLOAD
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_OSCILLATION_ON, default=OSCILLATE_ON_PAYLOAD
            ): cv.string,
            vol.Optional(CONF_SPEED_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(
                CONF_SPEED_LIST,
                default=[SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH],
            ): cv.ensure_list,
            vol.Optional(CONF_SPEED_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_SPEED_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
        }
    ).extend(MQTT_ENTITY_COMMON_SCHEMA.schema),
    valid_fan_speed_configuration,
    valid_speed_range_configuration,
    valid_preset_mode_configuration,
)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT fan through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT fan dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, fan.DOMAIN, setup, PLATFORM_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT fan."""
    async_add_entities([MqttFan(hass, config, config_entry, discovery_data)])


class MqttFan(MqttEntity, FanEntity):
    """A MQTT fan component."""

    _attributes_extra_blocked = MQTT_FAN_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT fan."""
        self._state = False
        # self._speed will be removed after a quarter (2021.7)
        self._speed = None
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
        self._optimistic_speed = None

        self._legacy_speeds_list = []
        self._legacy_speeds_list_no_off = []

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return PLATFORM_SCHEMA

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
                CONF_SPEED_STATE_TOPIC,
                CONF_SPEED_COMMAND_TOPIC,
                CONF_OSCILLATION_STATE_TOPIC,
                CONF_OSCILLATION_COMMAND_TOPIC,
            )
        }
        self._value_templates = {
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
            ATTR_PERCENTAGE: config.get(CONF_PERCENTAGE_VALUE_TEMPLATE),
            ATTR_PRESET_MODE: config.get(CONF_PRESET_MODE_VALUE_TEMPLATE),
            # ATTR_SPEED is deprecated in the schema, support will be removed after a quarter (2021.7)
            ATTR_SPEED: config.get(CONF_SPEED_VALUE_TEMPLATE),
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
            # The use of legacy speeds is deprecated in the schema, support will be removed after a quarter (2021.7)
            "SPEED_LOW": config[CONF_PAYLOAD_LOW_SPEED],
            "SPEED_MEDIUM": config[CONF_PAYLOAD_MEDIUM_SPEED],
            "SPEED_HIGH": config[CONF_PAYLOAD_HIGH_SPEED],
            "SPEED_OFF": config[CONF_PAYLOAD_OFF_SPEED],
            "PERCENTAGE_RESET": config[CONF_PAYLOAD_RESET_PERCENTAGE],
            "PRESET_MODE_RESET": config[CONF_PAYLOAD_RESET_PRESET_MODE],
        }
        # The use of legacy speeds is deprecated in the schema, support will be removed after a quarter (2021.7)
        self._feature_legacy_speeds = not self._topic[CONF_SPEED_COMMAND_TOPIC] is None
        if self._feature_legacy_speeds:
            self._legacy_speeds_list = config[CONF_SPEED_LIST]
            self._legacy_speeds_list_no_off = speed_list_without_preset_modes(
                self._legacy_speeds_list
            )

        self._feature_percentage = CONF_PERCENTAGE_COMMAND_TOPIC in config
        self._feature_preset_mode = CONF_PRESET_MODE_COMMAND_TOPIC in config
        if self._feature_preset_mode:
            self._preset_modes = config[CONF_PRESET_MODES_LIST]
        else:
            self._preset_modes = []

        if self._feature_percentage:
            self._speed_count = min(int_states_in_range(self._speed_range), 100)
        else:
            self._speed_count = len(self._legacy_speeds_list_no_off) or 100

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
        self._optimistic_speed = (
            optimistic or self._topic[CONF_SPEED_STATE_TOPIC] is None
        )

        self._supported_features = 0
        self._supported_features |= (
            self._topic[CONF_OSCILLATION_COMMAND_TOPIC] is not None
            and SUPPORT_OSCILLATE
        )
        if self._feature_percentage or self._feature_legacy_speeds:
            self._supported_features |= SUPPORT_SET_SPEED
        if self._feature_preset_mode:
            self._supported_features |= SUPPORT_PRESET_MODE

        for tpl_dict in [self._command_templates, self._value_templates]:
            for key, tpl in tpl_dict.items():
                if tpl is None:
                    tpl_dict[key] = lambda value: value
                else:
                    tpl.hass = self.hass
                    tpl_dict[key] = tpl.async_render_with_possible_json_value

    async def _subscribe_topics(self):  # noqa: C901
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
            self.async_write_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            topics[CONF_STATE_TOPIC] = {
                "topic": self._topic[CONF_STATE_TOPIC],
                "msg_callback": state_received,
                "qos": self._config[CONF_QOS],
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
                self._speed = None
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
            }
            self._preset_mode = None

        # The use of legacy speeds is deprecated in the schema, support will be removed after a quarter (2021.7)
        @callback
        @log_messages(self.hass, self.entity_id)
        def speed_received(msg):
            """Handle new received MQTT message for the speed."""
            speed_payload = self._value_templates[ATTR_SPEED](msg.payload)
            if speed_payload == self._payload["SPEED_LOW"]:
                speed = SPEED_LOW
            elif speed_payload == self._payload["SPEED_MEDIUM"]:
                speed = SPEED_MEDIUM
            elif speed_payload == self._payload["SPEED_HIGH"]:
                speed = SPEED_HIGH
            elif speed_payload == self._payload["SPEED_OFF"]:
                speed = SPEED_OFF
            else:
                speed = None

            if speed and speed in self._legacy_speeds_list:
                self._speed = speed
            else:
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid speed",
                    msg.payload,
                    msg.topic,
                    speed,
                )
                return

            if speed in self._legacy_speeds_list_no_off:
                self._percentage = ordered_list_item_to_percentage(
                    self._legacy_speeds_list_no_off, speed
                )
            elif speed == SPEED_OFF:
                self._percentage = 0

            self.async_write_ha_state()

        if self._topic[CONF_SPEED_STATE_TOPIC] is not None:
            topics[CONF_SPEED_STATE_TOPIC] = {
                "topic": self._topic[CONF_SPEED_STATE_TOPIC],
                "msg_callback": speed_received,
                "qos": self._config[CONF_QOS],
            }
            self._speed = SPEED_OFF

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
            }
            self._oscillation = False

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    # The use of legacy speeds is deprecated in the schema, support will be removed after a quarter (2021.7)
    @property
    def _implemented_speed(self) -> bool:
        """Return true if speed has been implemented."""
        return self._feature_legacy_speeds

    @property
    def percentage(self):
        """Return the current percentage."""
        return self._percentage

    @property
    def preset_mode(self):
        """Return the current preset _mode."""
        return self._preset_mode

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset modes."""
        return self._preset_modes

    # The speed_list property is deprecated in the schema, support will be removed after a quarter (2021.7)
    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._legacy_speeds_list_no_off

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._speed_count

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillation

    # The speed attribute deprecated in the schema, support will be removed after a quarter (2021.7)
    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the entity.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[CONF_STATE](self._payload["STATE_ON"])
        mqtt.async_publish(
            self.hass,
            self._topic[CONF_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if percentage:
            await self.async_set_percentage(percentage)
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        # The speed attribute deprecated in the schema, support will be removed after a quarter (2021.7)
        if speed and not percentage and not preset_mode:
            await self.async_set_speed(speed)
        if self._optimistic:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[CONF_STATE](self._payload["STATE_OFF"])
        mqtt.async_publish(
            self.hass,
            self._topic[CONF_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
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
        # Legacy are deprecated in the schema, support will be removed after a quarter (2021.7)
        if self._feature_legacy_speeds:
            if percentage:
                await self.async_set_speed(
                    percentage_to_ordered_list_item(
                        self._legacy_speeds_list_no_off,
                        percentage,
                    )
                )
            elif SPEED_OFF in self._legacy_speeds_list:
                await self.async_set_speed(SPEED_OFF)

        if self._feature_percentage:
            mqtt.async_publish(
                self.hass,
                self._topic[CONF_PERCENTAGE_COMMAND_TOPIC],
                mqtt_payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
            )

        if self._optimistic_percentage:
            self._percentage = percentage
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan.

        This method is a coroutine.
        """
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return

        mqtt_payload = self._command_templates[ATTR_PRESET_MODE](preset_mode)

        mqtt.async_publish(
            self.hass,
            self._topic[CONF_PRESET_MODE_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic_preset_mode:
            self._preset_mode = preset_mode
            self.async_write_ha_state()

    # async_set_speed is deprecated, support will be removed after a quarter (2021.7)
    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan.

        This method is a coroutine.
        """
        speed_payload = None
        if speed in self._legacy_speeds_list:
            if speed == SPEED_LOW:
                speed_payload = self._payload["SPEED_LOW"]
            elif speed == SPEED_MEDIUM:
                speed_payload = self._payload["SPEED_MEDIUM"]
            elif speed == SPEED_HIGH:
                speed_payload = self._payload["SPEED_HIGH"]
            else:
                speed_payload = self._payload["SPEED_OFF"]
        else:
            _LOGGER.warning("'%s' is not a valid speed", speed)
            return

        if speed_payload:
            mqtt.async_publish(
                self.hass,
                self._topic[CONF_SPEED_COMMAND_TOPIC],
                speed_payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
            )

            if self._optimistic_speed and speed_payload:
                self._speed = speed
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

        mqtt.async_publish(
            self.hass,
            self._topic[CONF_OSCILLATION_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic_oscillation:
            self._oscillation = oscillating
            self.async_write_ha_state()
