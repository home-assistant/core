"""
Camera that loads a picture from an MQTT topic.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.mqtt/
"""

import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import mqtt
from homeassistant.const import CONF_NAME
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_TOPIC = 'topic'
DEFAULT_NAME = 'MQTT Camera'

DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the MQTT Camera."""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    async_add_devices([MqttCamera(
        config.get(CONF_NAME),
        config.get(CONF_TOPIC)
    )])


class MqttCamera(Camera):
    """representation of a MQTT camera."""

    def __init__(self, name, topic):
        """Initialize the MQTT Camera."""
        super().__init__()

        self._name = name
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

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe MQTT events."""
        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT messages."""
            self._last_image = payload

        return mqtt.async_subscribe(
            self.hass, self._topic, message_received, self._qos, None)
