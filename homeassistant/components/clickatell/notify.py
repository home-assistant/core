"""
Clickatell platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.clickatell/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_RECIPIENT
import homeassistant.helpers.config_validation as cv

from . import PLATFORM_SCHEMA, BaseNotificationService

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'clickatell'

BASE_API_URL = 'https://platform.clickatell.com/messages/http/send'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Clickatell notification service."""
    return ClickatellNotificationService(config)


class ClickatellNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Clickatell service."""

    def __init__(self, config):
        """Initialize the service."""
        self.api_key = config.get(CONF_API_KEY)
        self.recipient = config.get(CONF_RECIPIENT)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {
            'apiKey': self.api_key,
            'to': self.recipient,
            'content': message,
        }

        resp = requests.get(BASE_API_URL, params=data, timeout=5)
        if (resp.status_code != 200) or (resp.status_code != 201):
            _LOGGER.error("Error %s : %s", resp.status_code, resp.text)
