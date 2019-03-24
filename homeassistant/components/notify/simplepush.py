"""
Simplepush notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.simplepush/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

from . import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)

REQUIREMENTS = ['simplepush==1.1.4']

_LOGGER = logging.getLogger(__name__)

ATTR_ENCRYPTED = 'encrypted'

CONF_DEVICE_KEY = 'device_key'
CONF_EVENT = 'event'
CONF_SALT = 'salt'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_KEY): cv.string,
    vol.Optional(CONF_EVENT): cv.string,
    vol.Inclusive(CONF_PASSWORD, ATTR_ENCRYPTED): cv.string,
    vol.Inclusive(CONF_SALT, ATTR_ENCRYPTED): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Simplepush notification service."""
    return SimplePushNotificationService(config)


class SimplePushNotificationService(BaseNotificationService):
    """Implementation of the notification service for Simplepush."""

    def __init__(self, config):
        """Initialize the Simplepush notification service."""
        self._device_key = config.get(CONF_DEVICE_KEY)
        self._event = config.get(CONF_EVENT)
        self._password = config.get(CONF_PASSWORD)
        self._salt = config.get(CONF_SALT)

    def send_message(self, message='', **kwargs):
        """Send a message to a Simplepush user."""
        from simplepush import send, send_encrypted

        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        if self._password:
            send_encrypted(self._device_key, self._password, self._salt, title,
                           message, event=self._event)
        else:
            send(self._device_key, title, message, event=self._event)
