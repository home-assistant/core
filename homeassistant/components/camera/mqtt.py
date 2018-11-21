"""
Camera that loads a picture from an MQTT topic.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.mqtt/
"""

import asyncio
import logging

import voluptuous as vol

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.components import mqtt, camera
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_TOPIC = 'topic'
CONF_UNIQUE_ID = 'unique_id'
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
    await _async_setup_entity(hass, config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT camera dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT camera."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(hass, config, async_add_entities)

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(camera.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(hass, config, async_add_entities):
    """Set up the MQTT Camera."""
    async_add_entities([MqttCamera(
        config.get(CONF_NAME),
        config.get(CONF_UNIQUE_ID),
        config.get(CONF_TOPIC)
    )])


class MqttCamera(Camera):
    """representation of a MQTT camera."""

    def __init__(self, name, unique_id, topic):
        """Initialize the MQTT Camera."""
        super().__init__()

        self._name = name
        self._unique_id = unique_id
        self._topic = topic
        self._qos = 0
        self._last_image = None

    @asyncio.coroutine
    def async_camera_image(self):
        """Return image response."""
        return self._last_image

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    async def async_added_to_hass(self):
        """Subscribe MQTT events."""
        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT messages."""
            self._last_image = payload

        await mqtt.async_subscribe(
            self.hass, self._topic, message_received, self._qos, None)
