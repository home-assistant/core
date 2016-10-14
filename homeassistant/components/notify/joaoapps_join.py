"""
Join platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.join/
"""
import logging
import voluptuous as vol
from homeassistant.components.notify import (
    ATTR_DATA, ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA,
    BaseNotificationService)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'https://github.com/nkgilley/python-join-api/archive/'
    '3e1e849f1af0b4080f551b62270c6d244d5fbcbd.zip#python-join-api==0.0.1']

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE_ID = 'device_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Optional(CONF_API_KEY): cv.string
})


# pylint: disable=unused-variable
def get_service(hass, config):
    """Get the Join notification service."""
    device_id = config.get(CONF_DEVICE_ID)
    api_key = config.get(CONF_API_KEY)
    if api_key:
        from pyjoin import get_devices
        if not get_devices(api_key):
            _LOGGER.error("Error connecting to Join, check API key")
            return False
    return JoinNotificationService(device_id, api_key)


# pylint: disable=too-few-public-methods
class JoinNotificationService(BaseNotificationService):
    """Implement the notification service for Join."""

    def __init__(self, device_id, api_key=None):
        """Initialize the service."""
        self._device_id = device_id
        self._api_key = api_key

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from pyjoin import send_notification
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA) or {}
        send_notification(device_id=self._device_id,
                          text=message,
                          title=title,
                          icon=data.get('icon'),
                          smallicon=data.get('smallicon'),
                          api_key=self._api_key)
