"""Support for MQTT fans."""
import functools
import logging

import voluptuous as vol

from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_SPEED,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    FanEntity,
    NotValidPresetModeError,
    NotValidSpeedError,
    speed_list_without_preset_modes,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_STATE,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util.percentage import (
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

_LOGGER = logging.getLogger(__name__)

CONF_STATE_VALUE_TEMPLATE = "state_value_template"
CONF_PERCENTAGE_STATE_TOPIC = "percentage_state_topic"
CONF_PERCENTAGE_COMMAND_TOPIC = "percentage_command_topic"
CONF_PERCENTAGE_VALUE_TEMPLATE = "percentage_value_template"
CONF_SPEED_RANGE_MIN = "speed_range_min"
CONF_SPEED_RANGE_MAX = "speed_range_max"
CONF_PRESET_MODE_STATE_TOPIC = "preset_mode_state_topic"
CONF_PRESET_MODE_COMMAND_TOPIC = "preset_mode_command_topic"
CONF_PRESET_MODE_VALUE_TEMPLATE = "preset_mode_value_template"
CONF_PRESET_MODES_LIST = "preset_modes"
CONF_SPEED_STATE_TOPIC = "speed_state_topic"
CONF_SPEED_COMMAND_TOPIC = "speed_command_topic"
CONF_SPEED_VALUE_TEMPLATE = "speed_value_template"
CONF_OSCILLATION_STATE_TOPIC = "oscillation_state_topic"
CONF_OSCILLATION_COMMAND_TOPIC = "oscillation_command_topic"
CONF_OSCILLATION_VALUE_TEMPLATE = "oscillation_value_template"
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
DEFAULT_OPTIMISTIC = False
DEFAULT_PRESET_MODES = ["auto"]
DEFAULT_SPEED_RANGE_MIN = 1
DEFAULT_SPEED_RANGE_MAX = 100

OSCILLATE_ON_PAYLOAD = "oscillate_on"
OSCILLATE_OFF_PAYLOAD = "oscillate_off"

OSCILLATION = "oscillation"

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_OSCILLATION_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_OSCILLATION_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_OSCILLATION_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_PERCENTAGE_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_PERCENTAGE_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_PERCENTAGE_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_PRESET_MODE_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_PRESET_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_PRESET_MODE_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_PRESET_MODES_LIST, default=[]): cv.ensure_list,
        vol.Optional(
            CONF_SPEED_RANGE_MIN, default=DEFAULT_SPEED_RANGE_MIN
        ): cv.positive_int,
        vol.Optional(
            CONF_SPEED_RANGE_MAX, default=DEFAULT_SPEED_RANGE_MAX
        ): cv.positive_int,
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
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
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

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT fan."""
        self._state = False
        self._speed = None
        self._percentage = None
        self._preset_mode = None
        self._oscillation = None
        self._supported_features = 0

        self._topic = None
        self._payload = None
        self._templates = None
        self._optimistic = None
        self._optimistic_oscillation = None
        self._optimistic_percentage = None
        self._optimistic_preset_mode = None
        self._optimistic_speed = None
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
        self._templates = {
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
            ATTR_PERCENTAGE: config.get(CONF_PERCENTAGE_VALUE_TEMPLATE),
            ATTR_PRESET_MODE: config.get(CONF_PRESET_MODE_VALUE_TEMPLATE),
            ATTR_SPEED: config.get(CONF_SPEED_VALUE_TEMPLATE),
            OSCILLATION: config.get(CONF_OSCILLATION_VALUE_TEMPLATE),
        }
        self._payload = {
            "STATE_ON": config[CONF_PAYLOAD_ON],
            "STATE_OFF": config[CONF_PAYLOAD_OFF],
            "OSCILLATE_ON_PAYLOAD": config[CONF_PAYLOAD_OSCILLATION_ON],
            "OSCILLATE_OFF_PAYLOAD": config[CONF_PAYLOAD_OSCILLATION_OFF],
            "SPEED_LOW": config[CONF_PAYLOAD_LOW_SPEED],
            "SPEED_MEDIUM": config[CONF_PAYLOAD_MEDIUM_SPEED],
            "SPEED_HIGH": config[CONF_PAYLOAD_HIGH_SPEED],
            "SPEED_OFF": config[CONF_PAYLOAD_OFF_SPEED],
        }
        if not self._topic[CONF_SPEED_COMMAND_TOPIC] is None:
            self._feature_speeds = 1
            _LOGGER.warning(
                "Using speeds is deprecated, use preset modes or percentage instead"
            )
        else:
            self._feature_speeds = 0

        if not self._topic[CONF_PERCENTAGE_COMMAND_TOPIC] is None:
            self._feature_percentage = 1
        else:
            self._feature_percentage = 0

        if not self._topic[CONF_PRESET_MODE_COMMAND_TOPIC] is None:
            self._feature_preset_mode = 1
        else:
            self._feature_preset_mode = 0
        if not config[CONF_PRESET_MODES_LIST] and self._feature_preset_mode:
            self._feature_preset_mode = 0
            raise ValueError("No preset_modes configured, preset mode feature disabled")

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
        self._supported_features |= (
            self._topic[CONF_PERCENTAGE_COMMAND_TOPIC] is not None and SUPPORT_SET_SPEED
        )
        self._supported_features |= (
            self._topic[CONF_PRESET_MODE_COMMAND_TOPIC] is not None
            and SUPPORT_SET_SPEED
        )
        self._supported_features |= (
            self._topic[CONF_SPEED_COMMAND_TOPIC] is not None and SUPPORT_SET_SPEED
        )

        for key, tpl in list(self._templates.items()):
            if tpl is None:
                self._templates[key] = lambda value: value
            else:
                tpl.hass = self.hass
                self._templates[key] = tpl.async_render_with_possible_json_value

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg):
            """Handle new received MQTT message."""
            payload = self._templates[CONF_STATE](msg.payload)
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
            payload = self._templates[ATTR_PERCENTAGE](msg.payload)
            percentage = ranged_value_to_percentage(self._speed_range, int(payload))
            if 0 <= percentage <= 100:
                self._percentage = percentage
            else:
                raise ValueError(f"{msg.payload} is not a valid percentage")
            self._state = bool(percentage)
            self.async_write_ha_state()

        if self._topic[CONF_PERCENTAGE_STATE_TOPIC] is not None:
            topics[CONF_PERCENTAGE_STATE_TOPIC] = {
                "topic": self._topic[CONF_PERCENTAGE_STATE_TOPIC],
                "msg_callback": percentage_received,
                "qos": self._config[CONF_QOS],
            }

        @callback
        @log_messages(self.hass, self.entity_id)
        def preset_mode_received(msg):
            """Handle new received MQTT message for preset mode."""
            payload = self._templates[ATTR_PRESET_MODE](msg.payload)
            if payload in self.preset_modes:
                self._preset_mode = str(payload)
                self._state = bool(self._percentage)
            else:
                raise NotValidPresetModeError(
                    f"{msg.payload} is not a valid preset mode"
                )

            self.async_write_ha_state()

        if self._topic[CONF_PRESET_MODE_STATE_TOPIC] is not None:
            topics[CONF_PRESET_MODE_STATE_TOPIC] = {
                "topic": self._topic[CONF_PRESET_MODE_STATE_TOPIC],
                "msg_callback": preset_mode_received,
                "qos": self._config[CONF_QOS],
            }
            self._preset_mode = None

        @callback
        @log_messages(self.hass, self.entity_id)
        def speed_received(msg):
            """Handle new received MQTT message for the speed."""
            payload = self._templates[ATTR_SPEED](msg.payload)
            if payload == self._payload["SPEED_LOW"]:
                self._speed = SPEED_LOW
            elif payload == self._payload["SPEED_MEDIUM"]:
                self._speed = SPEED_MEDIUM
            elif payload == self._payload["SPEED_HIGH"]:
                self._speed = SPEED_HIGH
            elif payload == self._payload["SPEED_OFF"]:
                self._speed = SPEED_OFF
                self._percentage = 0
            else:
                raise NotValidSpeedError(f"{payload} is not a valid speed")
            speed_list = speed_list_without_preset_modes(self.speed_list)
            if payload in speed_list:
                self._percentage = ordered_list_item_to_percentage(
                    speed_list_without_preset_modes(self.speed_list), payload
                )
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
            payload = self._templates[OSCILLATION](msg.payload)
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
        return self._config[CONF_PRESET_MODES_LIST]

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        speeds = []
        if self._feature_speeds:
            speeds += self._config[CONF_SPEED_LIST]
        if self._feature_preset_mode:
            speeds += self.preset_modes
        return speeds

    @property
    def _speed_list_without_preset_modes(self) -> list:
        """Return the speed list without preset modes.

        This property provides forward and backwards
        compatibility for conversion to percentage speeds.
        """
        return speed_list_without_preset_modes(self._config[CONF_SPEED_LIST])

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillation

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
        mqtt.async_publish(
            self.hass,
            self._topic[CONF_COMMAND_TOPIC],
            self._payload["STATE_ON"],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if percentage:
            await self.async_set_percentage(percentage)
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        if speed:
            await self.async_set_speed(speed)
        if self._optimistic:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._topic[CONF_COMMAND_TOPIC],
            self._payload["STATE_OFF"],
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
        mqtt_payload = int(percentage_to_ranged_value(self._speed_range, percentage))
        if self._feature_speeds:
            await self.async_set_speed(
                percentage_to_ordered_list_item(self.speed_list, percentage)
            )
            if self._optimistic_speed:
                self._percentage = percentage
                self.async_write_ha_state()
            return
        if self._feature_preset_mode:
            await self.async_set_preset_mode(
                percentage_to_ordered_list_item(self.preset_modes, percentage)
            )
            if self._optimistic_preset_mode:
                self._percentage = percentage
                self.async_write_ha_state()
            return

        if self._topic[CONF_PERCENTAGE_COMMAND_TOPIC] is not None:
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

        if preset_mode not in self._config[CONF_PRESET_MODES_LIST]:
            raise NotValidSpeedError(f"{preset_mode} is not a valid preset mode")

        mqtt_payload = preset_mode

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

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan.

        This method is a coroutine.
        """
        if speed == SPEED_LOW:
            mqtt_payload = self._payload["SPEED_LOW"]
        elif speed == SPEED_MEDIUM:
            mqtt_payload = self._payload["SPEED_MEDIUM"]
        elif speed == SPEED_HIGH:
            mqtt_payload = self._payload["SPEED_HIGH"]
        elif speed == SPEED_OFF:
            mqtt_payload = self._payload["SPEED_OFF"]
        elif (
            self._feature_preset_mode and speed in self._config[CONF_PRESET_MODES_LIST]
        ):
            percentage = ordered_list_item_to_percentage(
                self._config[CONF_PRESET_MODES_LIST], speed
            )
            mqtt_payload = percentage_to_ordered_list_item(
                self._speed_list_without_preset_modes, percentage
            )
        #        elif self._feature_percentage:
        #            percentage = int(speed)
        #            if percentage:
        #                mqtt_payload = percentage_to_ordered_list_item(
        #                    self._speed_list_without_preset_modes, percentage
        #                )
        else:
            raise NotValidSpeedError(f"{speed} is not a valid fan speed")
        if self._topic[CONF_SPEED_COMMAND_TOPIC] is not None:
            mqtt.async_publish(
                self.hass,
                self._topic[CONF_SPEED_COMMAND_TOPIC],
                mqtt_payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
            )

        if self._optimistic_speed:
            self._speed = speed
            self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation.

        This method is a coroutine.
        """
        if oscillating is False:
            payload = self._payload["OSCILLATE_OFF_PAYLOAD"]
        else:
            payload = self._payload["OSCILLATE_ON_PAYLOAD"]

        mqtt.async_publish(
            self.hass,
            self._topic[CONF_OSCILLATION_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic_oscillation:
            self._oscillation = oscillating
            self.async_write_ha_state()
