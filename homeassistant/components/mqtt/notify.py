"""Support for MQTT notification."""
import json
import logging

import voluptuous as vol

from homeassistant.components.mqtt import valid_publish_topic
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)

CONF_TOPIC_NAME = "topic"

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({vol.Required(CONF_TOPIC_NAME): valid_publish_topic,}),
)

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the notification service."""

    return MqttNotificationService(config)


class MqttNotificationService(BaseNotificationService):
    """Implement the notification service for the MQTT topic."""

    def __init__(self, config):
        """Initialize the service."""
        self.topic = config[CONF_TOPIC_NAME]

    async def async_send_message(self, message, **kwargs):
        """Send a message."""
        dto = {ATTR_MESSAGE: message}

        if ATTR_TITLE in kwargs:
            dto[ATTR_TITLE] = kwargs[ATTR_TITLE]
        if ATTR_TARGET in kwargs:
            dto[ATTR_TARGET] = kwargs[ATTR_TARGET]

        data = kwargs.get(ATTR_DATA)
        if data:
            dto.update(data)

        topic_message = json.dumps(dto)
        self.hass.components.mqtt.publish(self.topic, topic_message)
