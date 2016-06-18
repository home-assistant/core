"""
Join platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.Join/
"""
import logging
import voluptuous as vol
from homeassistant.components.notify import (
    ATTR_DATA, ATTR_TITLE, BaseNotificationService)
from homeassistant.const import CONF_PLATFORM, CONF_NAME, CONF_API_KEY
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'https://github.com/nkgilley/python-join-api/archive/'
    'ceb384eb21e2b103fc0c355447252fedd7f7a185.zip#python-join-api==0.0.1']

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE_ID = 'device_id'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'joaoapps_join',
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Optional(CONF_NAME): cv.string,
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
        from pyjoin import (send_notification, ring_device, send_sms, send_url,
                            set_wallpaper, send_file)
        title = kwargs.get(ATTR_TITLE)
        data = kwargs.get(ATTR_DATA)
        action = 'notify'
        if data:
            action = data.get('action')
            url = data.get('url')
            sms_number = data.get('sms_number')
        if action == 'notify':
            send_notification(self._device_id, text=message,
                              title=title, api_key=self._api_key)
        elif action == 'ring':
            ring_device(self._device_id, api_key=self._api_key)
        elif action == 'wallpaper':
            set_wallpaper(self._device_id, url, api_key=self._api_key)
        elif action == 'sms':
            send_sms(self._device_id, sms_number, message,
                     api_key=self._api_key)
        elif action == 'file':
            send_file(self._device_id, url=url, api_key=self._api_key)
        elif action == 'url':
            send_url(self._device_id, url=url, api_key=self._api_key)
