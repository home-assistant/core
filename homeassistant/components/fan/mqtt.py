"""
Support for MQTT fans.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/fan.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import fan, mqtt
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_STATE, STATE_ON, STATE_OFF,
    CONF_PAYLOAD_OFF, CONF_PAYLOAD_ON, CONF_DEVICE)
from homeassistant.components.mqtt import (
    ATTR_DISCOVERY_HASH, CONF_AVAILABILITY_TOPIC, CONF_STATE_TOPIC,
    CONF_COMMAND_TOPIC, CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE,
    CONF_QOS, CONF_RETAIN, MqttAvailability, MqttDiscoveryUpdate,
    MqttEntityDeviceInfo, subscription)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.components.fan import (SPEED_LOW, SPEED_MEDIUM,
                                          SPEED_HIGH, FanEntity,
                                          SUPPORT_SET_SPEED, SUPPORT_OSCILLATE,
                                          SPEED_OFF, ATTR_SPEED)
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_STATE_VALUE_TEMPLATE = 'state_value_template'
CONF_SPEED_STATE_TOPIC = 'speed_state_topic'
CONF_SPEED_COMMAND_TOPIC = 'speed_command_topic'
CONF_SPEED_VALUE_TEMPLATE = 'speed_value_template'
CONF_OSCILLATION_STATE_TOPIC = 'oscillation_state_topic'
CONF_OSCILLATION_COMMAND_TOPIC = 'oscillation_command_topic'
CONF_OSCILLATION_VALUE_TEMPLATE = 'oscillation_value_template'
CONF_PAYLOAD_OSCILLATION_ON = 'payload_oscillation_on'
CONF_PAYLOAD_OSCILLATION_OFF = 'payload_oscillation_off'
CONF_PAYLOAD_LOW_SPEED = 'payload_low_speed'
CONF_PAYLOAD_MEDIUM_SPEED = 'payload_medium_speed'
CONF_PAYLOAD_HIGH_SPEED = 'payload_high_speed'
CONF_SPEED_LIST = 'speeds'
CONF_UNIQUE_ID = 'unique_id'

DEFAULT_NAME = 'MQTT Fan'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_OPTIMISTIC = False

OSCILLATE_ON_PAYLOAD = 'oscillate_on'
OSCILLATE_OFF_PAYLOAD = 'oscillate_off'

OSCILLATION = 'oscillation'

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_SPEED_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_SPEED_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_SPEED_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_OSCILLATION_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_OSCILLATION_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_OSCILLATION_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_OSCILLATION_ON,
                 default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OSCILLATION_OFF,
                 default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_LOW_SPEED, default=SPEED_LOW): cv.string,
    vol.Optional(CONF_PAYLOAD_MEDIUM_SPEED, default=SPEED_MEDIUM): cv.string,
    vol.Optional(CONF_PAYLOAD_HIGH_SPEED, default=SPEED_HIGH): cv.string,
    vol.Optional(CONF_SPEED_LIST,
                 default=[SPEED_OFF, SPEED_LOW,
                          SPEED_MEDIUM, SPEED_HIGH]): cv.ensure_list,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT fan through configuration.yaml."""
    await _async_setup_entity(hass, config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT fan dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT fan."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_payload[ATTR_DISCOVERY_HASH])

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(fan.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT fan."""
    async_add_entities([MqttFan(
        config,
        discovery_hash,
    )])


class MqttFan(MqttAvailability, MqttDiscoveryUpdate, MqttEntityDeviceInfo,
              FanEntity):
    """A MQTT fan component."""

    def __init__(self, config, discovery_hash):
        """Initialize the MQTT fan."""
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._state = False
        self._speed = None
        self._oscillation = None
        self._supported_features = 0
        self._sub_state = None

        self._topic = None
        self._payload = None
        self._templates = None
        self._optimistic = None
        self._optimistic_oscillation = None
        self._optimistic_speed = None

        # Load config
        self._setup_from_config(config)

        availability_topic = config.get(CONF_AVAILABILITY_TOPIC)
        payload_available = config.get(CONF_PAYLOAD_AVAILABLE)
        payload_not_available = config.get(CONF_PAYLOAD_NOT_AVAILABLE)
        qos = config.get(CONF_QOS)
        device_config = config.get(CONF_DEVICE)

        MqttAvailability.__init__(self, availability_topic, qos,
                                  payload_available, payload_not_available)
        MqttDiscoveryUpdate.__init__(self, discovery_hash,
                                     self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config)

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA(discovery_payload)
        self._setup_from_config(config)
        await self.availability_discovery_update(config)
        await self._subscribe_topics()
        self.async_schedule_update_ha_state()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._config = config
        self._topic = {
            key: config.get(key) for key in (
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
            OSCILLATION: config.get(CONF_OSCILLATION_VALUE_TEMPLATE)
        }
        self._payload = {
            STATE_ON: config.get(CONF_PAYLOAD_ON),
            STATE_OFF: config.get(CONF_PAYLOAD_OFF),
            OSCILLATE_ON_PAYLOAD: config.get(CONF_PAYLOAD_OSCILLATION_ON),
            OSCILLATE_OFF_PAYLOAD: config.get(CONF_PAYLOAD_OSCILLATION_OFF),
            SPEED_LOW: config.get(CONF_PAYLOAD_LOW_SPEED),
            SPEED_MEDIUM: config.get(CONF_PAYLOAD_MEDIUM_SPEED),
            SPEED_HIGH: config.get(CONF_PAYLOAD_HIGH_SPEED),
        }
        optimistic = config.get(CONF_OPTIMISTIC)
        self._optimistic = optimistic or self._topic[CONF_STATE_TOPIC] is None
        self._optimistic_oscillation = (
            optimistic or self._topic[CONF_OSCILLATION_STATE_TOPIC] is None)
        self._optimistic_speed = (
            optimistic or self._topic[CONF_SPEED_STATE_TOPIC] is None)

        self._supported_features = 0
        self._supported_features |= (self._topic[CONF_OSCILLATION_STATE_TOPIC]
                                     is not None and SUPPORT_OSCILLATE)
        self._supported_features |= (self._topic[CONF_SPEED_STATE_TOPIC]
                                     is not None and SUPPORT_SET_SPEED)

        self._unique_id = config.get(CONF_UNIQUE_ID)

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}
        templates = {}
        for key, tpl in list(self._templates.items()):
            if tpl is None:
                templates[key] = lambda value: value
            else:
                tpl.hass = self.hass
                templates[key] = tpl.async_render_with_possible_json_value

        @callback
        def state_received(topic, payload, qos):
            """Handle new received MQTT message."""
            payload = templates[CONF_STATE](payload)
            if payload == self._payload[STATE_ON]:
                self._state = True
            elif payload == self._payload[STATE_OFF]:
                self._state = False
            self.async_schedule_update_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            topics[CONF_STATE_TOPIC] = {
                'topic': self._topic[CONF_STATE_TOPIC],
                'msg_callback': state_received,
                'qos': self._config.get(CONF_QOS)}

        @callback
        def speed_received(topic, payload, qos):
            """Handle new received MQTT message for the speed."""
            payload = templates[ATTR_SPEED](payload)
            if payload == self._payload[SPEED_LOW]:
                self._speed = SPEED_LOW
            elif payload == self._payload[SPEED_MEDIUM]:
                self._speed = SPEED_MEDIUM
            elif payload == self._payload[SPEED_HIGH]:
                self._speed = SPEED_HIGH
            self.async_schedule_update_ha_state()

        if self._topic[CONF_SPEED_STATE_TOPIC] is not None:
            topics[CONF_SPEED_STATE_TOPIC] = {
                'topic': self._topic[CONF_SPEED_STATE_TOPIC],
                'msg_callback': speed_received,
                'qos': self._config.get(CONF_QOS)}
            self._speed = SPEED_OFF

        @callback
        def oscillation_received(topic, payload, qos):
            """Handle new received MQTT message for the oscillation."""
            payload = templates[OSCILLATION](payload)
            if payload == self._payload[OSCILLATE_ON_PAYLOAD]:
                self._oscillation = True
            elif payload == self._payload[OSCILLATE_OFF_PAYLOAD]:
                self._oscillation = False
            self.async_schedule_update_ha_state()

        if self._topic[CONF_OSCILLATION_STATE_TOPIC] is not None:
            topics[CONF_OSCILLATION_STATE_TOPIC] = {
                'topic': self._topic[CONF_OSCILLATION_STATE_TOPIC],
                'msg_callback': oscillation_received,
                'qos': self._config.get(CONF_QOS)}
            self._oscillation = False

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state,
            topics)

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state)
        await MqttAvailability.async_will_remove_from_hass(self)

    @property
    def should_poll(self):
        """No polling needed for a MQTT fan."""
        return False

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
        return self._config.get(CONF_NAME)

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._config.get(CONF_SPEED_LIST)

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

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._topic[CONF_COMMAND_TOPIC],
            self._payload[STATE_ON], self._config.get(CONF_QOS),
            self._config.get(CONF_RETAIN))
        if speed:
            await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._topic[CONF_COMMAND_TOPIC],
            self._payload[STATE_OFF], self._config.get(CONF_QOS),
            self._config.get(CONF_RETAIN))

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan.

        This method is a coroutine.
        """
        if self._topic[CONF_SPEED_COMMAND_TOPIC] is None:
            return

        if speed == SPEED_LOW:
            mqtt_payload = self._payload[SPEED_LOW]
        elif speed == SPEED_MEDIUM:
            mqtt_payload = self._payload[SPEED_MEDIUM]
        elif speed == SPEED_HIGH:
            mqtt_payload = self._payload[SPEED_HIGH]
        else:
            mqtt_payload = speed

        mqtt.async_publish(
            self.hass, self._topic[CONF_SPEED_COMMAND_TOPIC],
            mqtt_payload, self._config.get(CONF_QOS),
            self._config.get(CONF_RETAIN))

        if self._optimistic_speed:
            self._speed = speed
            self.async_schedule_update_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation.

        This method is a coroutine.
        """
        if self._topic[CONF_OSCILLATION_COMMAND_TOPIC] is None:
            return

        if oscillating is False:
            payload = self._payload[OSCILLATE_OFF_PAYLOAD]
        else:
            payload = self._payload[OSCILLATE_ON_PAYLOAD]

        mqtt.async_publish(
            self.hass, self._topic[CONF_OSCILLATION_COMMAND_TOPIC],
            payload, self._config.get(CONF_QOS), self._config.get(CONF_RETAIN))

        if self._optimistic_oscillation:
            self._oscillation = oscillating
            self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id
