"""LlamaLab Automate notification service."""
from http import HTTPStatus
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY, CONF_DEVICE
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)
_RESOURCE = "https://llamalab.com/automate/cloud/message"

ATTR_PRIORITY = "priority"

CONF_TO = "to"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Optional(CONF_DEVICE): cv.string,
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the LlamaLab Automate notification service."""
    secret = config.get(CONF_API_KEY)
    recipient = config.get(CONF_TO)
    device = config.get(CONF_DEVICE)

    return AutomateNotificationService(secret, recipient, device)


class AutomateNotificationService(BaseNotificationService):
    """Implement the notification service for LlamaLab Automate."""

    def __init__(self, secret, recipient, device=None):
        """Initialize the service."""
        self._secret = secret
        self._recipient = recipient
        self._device = device

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        # Extract params from data dict
        data = dict(kwargs.get(ATTR_DATA) or {})
        priority = data.get(ATTR_PRIORITY, "normal").lower()

        _LOGGER.debug(
            "Sending to: %s, %s, prio: %s", self._recipient, str(self._device), priority
        )

        data = {
            "secret": self._secret,
            "to": self._recipient,
            "device": self._device,
            "priority": priority,
            "payload": message,
        }

        response = requests.post(_RESOURCE, json=data, timeout=10)
        if response.status_code != HTTPStatus.OK:
            _LOGGER.error("Error sending message: %s", response)
