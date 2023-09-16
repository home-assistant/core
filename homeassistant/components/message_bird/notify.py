"""MessageBird platform for notify component."""
from __future__ import annotations

import logging

import messagebird
from messagebird.client import ErrorException
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TARGET,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY, CONF_SENDER
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_SENDER, default="HA"): vol.All(
            cv.string, vol.Match(r"^(\+?[1-9]\d{1,14}|\w{1,11})$")
        ),
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MessageBirdNotificationService | None:
    """Get the MessageBird notification service."""
    client = messagebird.Client(config[CONF_API_KEY])
    try:
        # validates the api key
        client.balance()
    except messagebird.client.ErrorException:
        _LOGGER.error("The specified MessageBird API key is invalid")
        return None

    return MessageBirdNotificationService(config.get(CONF_SENDER), client)


class MessageBirdNotificationService(BaseNotificationService):
    """Implement the notification service for MessageBird."""

    def __init__(self, sender, client):
        """Initialize the service."""
        self.sender = sender
        self.client = client

    def send_message(self, message=None, **kwargs):
        """Send a message to a specified target."""
        if not (targets := kwargs.get(ATTR_TARGET)):
            _LOGGER.error("No target specified")
            return

        for target in targets:
            try:
                self.client.message_create(
                    self.sender, target, message, {"reference": "HA"}
                )
            except ErrorException as exception:
                _LOGGER.error("Failed to notify %s: %s", target, exception)
                continue
