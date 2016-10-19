"""
LaMetric platform for notify component.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.Lametric/
"""
import logging
import voluptuous as vol
from homeassistant.components.notify import (
    ATTR_DATA, ATTR_TARGET, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'https://github.com/heytcass/python-lametric-api/archive/'
    '2bb4f0e2ebf6c69818d0f404c8fee1d95b6fc808.zip#python-lametric-api==0.0.1']

_LOGGER = logging.getLogger(__name__)

CONF_HOST = 'host'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_HOST): cv.string
})


# pylint: disable=unused-variable
def get_service(hass, config):
    """Get the LaMetric notification service."""
    host = config.get(CONF_HOST)
    api_key = config.get(CONF_API_KEY)
    return LaMetricNotificationService(host, api_key)


# pylint: disable=too-few-public-methods
class LaMetricNotificationService(BaseNotificationService):
    """Implement the notification service for LaMetric."""

    def __init__(self, host, api_key=None):
        """Initialize the service."""
        self._host = host
        self._api_key = api_key

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from pylametric import send_notification
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA) or {}
        send_notification(host=self._host,
                          text=message,
                          api_key=self._api_key)
