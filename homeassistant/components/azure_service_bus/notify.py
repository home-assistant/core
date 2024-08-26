"""Support for azure service bus notification."""

from __future__ import annotations

import json
import logging

from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient, ServiceBusSender
from azure.servicebus.exceptions import (
    MessagingEntityNotFoundError,
    ServiceBusConnectionError,
    ServiceBusError,
)
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_CONNECTION_STRING = "connection_string"
CONF_QUEUE_NAME = "queue"
CONF_TOPIC_NAME = "topic"

ATTR_ASB_MESSAGE = "message"
ATTR_ASB_TITLE = "title"
ATTR_ASB_TARGET = "target"

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_QUEUE_NAME, CONF_TOPIC_NAME),
    NOTIFY_PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_CONNECTION_STRING): cv.string,
            vol.Exclusive(
                CONF_QUEUE_NAME, "output", "Can only send to a queue or a topic."
            ): cv.string,
            vol.Exclusive(
                CONF_TOPIC_NAME, "output", "Can only send to a queue or a topic."
            ): cv.string,
        }
    ),
)

_LOGGER = logging.getLogger(__name__)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ServiceBusNotificationService | None:
    """Get the notification service."""
    connection_string: str = config[CONF_CONNECTION_STRING]
    queue_name: str | None = config.get(CONF_QUEUE_NAME)
    topic_name: str | None = config.get(CONF_TOPIC_NAME)

    # Library can do synchronous IO when creating the clients.
    # Passes in loop here, but can't run setup on the event loop.
    servicebus = ServiceBusClient.from_connection_string(
        connection_string, loop=hass.loop
    )

    client: ServiceBusSender | None = None
    try:
        if queue_name:
            client = servicebus.get_queue_sender(queue_name)
        elif topic_name:
            client = servicebus.get_topic_sender(topic_name)
    except (ServiceBusConnectionError, MessagingEntityNotFoundError) as err:
        _LOGGER.error(
            "Connection error while creating client for queue/topic '%s'. %s",
            queue_name or topic_name,
            err,
        )
        return None

    return ServiceBusNotificationService(client) if client else None


class ServiceBusNotificationService(BaseNotificationService):
    """Implement the notification service for the service bus service."""

    def __init__(self, client):
        """Initialize the service."""
        self._client = client

    async def async_send_message(self, message, **kwargs):
        """Send a message."""
        dto = {ATTR_ASB_MESSAGE: message}

        if ATTR_TITLE in kwargs:
            dto[ATTR_ASB_TITLE] = kwargs[ATTR_TITLE]
        if ATTR_TARGET in kwargs:
            dto[ATTR_ASB_TARGET] = kwargs[ATTR_TARGET]

        if data := kwargs.get(ATTR_DATA):
            dto.update(data)

        queue_message = ServiceBusMessage(
            json.dumps(dto), content_type=CONTENT_TYPE_JSON
        )
        try:
            await self._client.send_messages(queue_message)
        except ServiceBusError as err:
            _LOGGER.error(
                "Could not send service bus notification to %s. %s",
                self._client.name,
                err,
            )
