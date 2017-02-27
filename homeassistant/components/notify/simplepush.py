"""
Simplepush notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.simplepush/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://api.simplepush.io/send'

CONF_DEVICE_KEY = 'device_key'

DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_KEY): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Simplepush notification service."""
    return SimplePushNotificationService(config.get(CONF_DEVICE_KEY))


class SimplePushNotificationService(BaseNotificationService):
    """Implementation of the notification service for SimplePush."""

    def __init__(self, device_key):
        """Initialize the service."""
        self._device_key = device_key

    def send_message(self, message='', **kwargs):
        """Send a message to a user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        # Upstream bug will be fixed soon, but no dead-line available.
        # payload = 'key={}&title={}&msg={}'.format(
        #     self._device_key, title, message).replace(' ', '%')
        # response = requests.get(
        #     _RESOURCE, data=payload, timeout=DEFAULT_TIMEOUT)
        response = requests.get(
            '{}/{}/{}/{}'.format(_RESOURCE, self._device_key, title, message),
            timeout=DEFAULT_TIMEOUT)

        if response.json()['status'] != 'OK':
            _LOGGER.error("Not possible to send notification")
