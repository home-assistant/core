"""
SynologyChat platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.synology_chat/
"""
import logging
import json

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    BaseNotificationService, PLATFORM_SCHEMA, ATTR_DATA)
from homeassistant.const import CONF_RESOURCE
import homeassistant.helpers.config_validation as cv

ATTR_FILE_URL = 'file_url'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
})

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the Synology Chat notification service."""
    resource = config.get(CONF_RESOURCE)

    return SynologyChatNotificationService(resource)


class SynologyChatNotificationService(BaseNotificationService):
    """Implementation of a notification service for Synology Chat."""

    def __init__(self, resource):
        """Initialize the service."""
        self._resource = resource

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {
            'text': message
        }

        extended_data = kwargs.get(ATTR_DATA)
        file_url = extended_data.get(ATTR_FILE_URL) if extended_data else None

        if file_url:
            data['file_url'] = file_url

        to_send = 'payload={}'.format(json.dumps(data))

        response = requests.post(self._resource, data=to_send, timeout=10)

        if response.status_code not in (200, 201):
            _LOGGER.exception(
                "Error sending message. Response %d: %s:",
                response.status_code, response.reason)
