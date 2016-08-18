"""
LlamaLab Automate notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.llamalab_automate/
"""
import logging
import requests

from homeassistant.components.notify import (
    DOMAIN, BaseNotificationService)
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://llamalab.com/automate/cloud/message'


def get_service(hass, config):
    """Get the LlamaLab Automate notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['secret', 'to']},
                           _LOGGER):
        return None

    return AutomateNotificationService(config['secret'], config['to'])


# pylint: disable=too-few-public-methods
class AutomateNotificationService(BaseNotificationService):
    """Implement the notification service for LlamaLab Automate."""

    def __init__(self, secret, to):
        """Initialize the service."""
        self._secret = secret
        self._to = to

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        _LOGGER.debug("Sending to: " + str(self._to))
        data = {
            "secret": self._secret,
            "to": self._to,
            "device": None,
            "payload": message,
        }

        response = requests.post(_RESOURCE, json=data)
        if response.status_code != 200:
            _LOGGER.error("Error sending message: " + str(response))
