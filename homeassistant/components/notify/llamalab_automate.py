"""
LlamaLab Automate notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.llamalab_automate/
"""
import logging
import requests
import voluptuous as vol

from homeassistant.components.notify import (
    BaseNotificationService, PLATFORM_SCHEMA)
from homeassistant.const import CONF_API_KEY, CONF_DEVICE
from homeassistant.helpers import config_validation as cv


_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://llamalab.com/automate/cloud/message'

CONF_TO = 'to'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_TO): cv.string,
    vol.Optional(CONF_DEVICE): cv.string,
})


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
        _LOGGER.debug("Sending to: %s, %s", self._recipient, str(self._device))
        data = {
            "secret": self._secret,
            "to": self._recipient,
            "device": self._device,
            "payload": message,
        }

        response = requests.post(_RESOURCE, json=data)
        if response.status_code != 200:
            _LOGGER.error("Error sending message: " + str(response))
