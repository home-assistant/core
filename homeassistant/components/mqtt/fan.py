"""Support for MQTT fans."""
import functools
import logging

import voluptuous as vol

from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_SPEED,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_STATE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

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
from .mixins import (
    MQTT_AVAILABILITY_SCHEMA,
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    MQTT_JSON_ATTRS_SCHEMA,
    MqttEntity,
    async_setup_entry_helper,
)

_LOGGER = logging.getLogger(__name__)

CONF_STATE_VALUE_TEMPLATE = "state_value_template"
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

OSCILLATE_ON_PAYLOAD = "oscillate_on"
OSCILLATE_OFF_PAYLOAD = "oscillate_off"

OSCILLATION = "oscillation"

PLATFORM_SCHEMA = (
    mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_OSCILLATION_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_OSCILLATION_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_OSCILLATION_VALUE_TEMPLATE): cv.template,
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
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(MQTT_JSON_ATTRS_SCHEMA.schema)
)


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
        self._oscillation = None
        self._supported_features = 0

        self._topic = None
        self._payload = None
        self._templates = None
        self._optimistic = None
        self._optimistic_oscillation = None
        self._optimistic_speed = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return PLATFORM_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._config = config
        self._topic = {
            key: config.get(key)
            for key in (
                CONF_STATE_TOPIC,
                CONF_COMMAND_TOPIC,
                CONF_SPEED_STATE_TOPIC,
                CONF_SPEED_COMMAND_TOPIC,
                CONF_OSCILLATION_STATE_TOPIC,
                CONF_OSCILLATION_COMMAND_TOPIC,
            )
        }
        self._templates = {
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
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
        optimistic = config[CONF_OPTIMISTIC]
        self._optimistic = optimistic or self._topic[CONF_STATE_TOPIC] is None
        self._optimistic_oscillation = (
            optimistic or self._topic[CONF_OSCILLATION_STATE_TOPIC] is None
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
    def name(self) -> str:
        """Get entity name."""
        return self._config[CONF_NAME]

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._config[CONF_SPEED_LIST]

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

    #
    # The fan entity model has changed to use percentages and preset_modes
    # instead of speeds.
    #
    # Please review
    # https://developers.home-assistant.io/docs/core/entity/fan/
    #
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
        else:
            raise ValueError(f"{speed} is not a valid fan speed")

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
