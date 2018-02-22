"""
RESTful platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.rest/
"""
import logging
import json

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT, BaseNotificationService,
    PLATFORM_SCHEMA)
from homeassistant.const import (CONF_RESOURCE, CONF_NAME)
import homeassistant.helpers.config_validation as cv


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Required(CONF_NAME): cv.string,
})

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the Synology Chat notification service."""
    resource = config.get(CONF_RESOURCE)

    return SynologyChatNotificationService(
        hass, resource)

class SynologyChatNotificationService(BaseNotificationService):
    """Implementation of a notification service for Synology Chat."""

    def __init__(self, hass, resource):
        """Initialize the service."""
        self._resource = resource
        self._hass = hass

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {
            'text': message 
        }

        to_send = 'payload=' + json.dumps(data)

        response = requests.post(self._resource, data=to_send, timeout=10)

        if response.status_code not in (200, 201):
            _LOGGER.exception(
                "Error sending message. Response %d: %s:",
                response.status_code, response.reason)
