"""
Pushsafer platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushsafer/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://www.pushsafer.com/api'

CONF_DEVICE_KEY = 'private_key'

DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_KEY): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Pushsafer.com notification service."""
    return PushsaferNotificationService(config.get(CONF_DEVICE_KEY))


class PushsaferNotificationService(BaseNotificationService):
    """Implementation of the notification service for Pushsafer.com."""

    def __init__(self, private_key):
        """Initialize the service."""
        self._private_key = private_key

    def send_message(self, message='', **kwargs):
        """Send a message to a user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        payload = {'k': self._private_key, 't': title, 'm': message}
        response = requests.get(_RESOURCE, params=payload,
                                timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            _LOGGER.error("Not possible to send notification")
