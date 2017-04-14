"""
Camera that loads a picture from an MQTT topic.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.mqtt/
"""

import logging
import asyncio

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt
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


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Camera."""
    topic = config[CONF_TOPIC]

    add_devices([MqttCamera(config[CONF_NAME], topic)])


class MqttCamera(Camera):
    """MQTT camera."""

    def __init__(self, name, topic):
        """Initialize Local File Camera component."""
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

    def async_added_to_hass(self):
        """Subscribe mqtt events.

        This method must be run in the event loop and returns a coroutine.
        """
        @callback
        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            self._last_image = payload

        return mqtt.async_subscribe(
            self.hass, self._topic, message_received, self._qos, None)
