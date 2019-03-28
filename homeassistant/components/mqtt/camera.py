"""
Camera that loads a picture from an MQTT topic.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.mqtt/
"""

import asyncio
import logging

import voluptuous as vol

from homeassistant.components import camera, mqtt
from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import (
    ATTR_DISCOVERY_HASH, CONF_STATE_TOPIC, CONF_UNIQUE_ID, MqttDiscoveryUpdate,
    subscription)
from .discovery import MQTT_DISCOVERY_NEW, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

CONF_TOPIC = 'topic'
DEFAULT_NAME = 'MQTT Camera'

DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT camera through configuration.yaml."""
    await _async_setup_entity(config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT camera dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT camera."""
        try:
            discovery_hash = discovery_payload.pop(ATTR_DISCOVERY_HASH)
            # state_topic is implicitly set by MQTT discovery, remove it
            discovery_payload.pop(CONF_STATE_TOPIC, None)
            config = PLATFORM_SCHEMA(discovery_payload)
            await _async_setup_entity(config, async_add_entities,
                                      discovery_hash)
        except Exception:
            if discovery_hash:
                clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(camera.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(config, async_add_entities, discovery_hash=None):
    """Set up the MQTT Camera."""
    async_add_entities([MqttCamera(config, discovery_hash)])


class MqttCamera(MqttDiscoveryUpdate, Camera):
    """representation of a MQTT camera."""

    def __init__(self, config, discovery_hash):
        """Initialize the MQTT Camera."""
        self._config = config
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._sub_state = None

        self._qos = 0
        self._last_image = None

        Camera.__init__(self)
        MqttDiscoveryUpdate.__init__(self, discovery_hash,
                                     self.discovery_update)

    async def async_added_to_hass(self):
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        # state_topic is implicitly set by MQTT discovery, remove it
        discovery_payload.pop(CONF_STATE_TOPIC, None)
        config = PLATFORM_SCHEMA(discovery_payload)
        self._config = config
        await self._subscribe_topics()
        self.async_write_ha_state()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            self._last_image = msg.payload

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state,
            {'state_topic': {'topic': self._config.get(CONF_TOPIC),
                             'msg_callback': message_received,
                             'qos': self._qos,
                             'encoding': None}})

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state)

    @asyncio.coroutine
    def async_camera_image(self):
        """Return image response."""
        return self._last_image

    @property
    def name(self):
        """Return the name of this camera."""
        return self._config.get(CONF_NAME)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id
