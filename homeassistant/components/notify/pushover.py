"""
Pushover platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushover/
"""
import logging

from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import validate_config

REQUIREMENTS = ['python-pushover==0.2']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-variable
def get_service(hass, config):
    """Get the Pushover notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['user_key', CONF_API_KEY]},
                           _LOGGER):
        return None

    from pushover import InitError

    try:
        return PushoverNotificationService(config['user_key'],
                                           config[CONF_API_KEY])
    except InitError:
        _LOGGER.error(
            "Wrong API key supplied. "
            "Get it at https://pushover.net")
        return None


# pylint: disable=too-few-public-methods
class PushoverNotificationService(BaseNotificationService):
    """Implement the notification service for Pushover."""

    def __init__(self, user_key, api_token):
        """Initialize the service."""
        from pushover import Client
        self._user_key = user_key
        self._api_token = api_token
        self.pushover = Client(
            self._user_key, api_token=self._api_token)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from pushover import RequestError

        try:
            self.pushover.send_message(message, title=kwargs.get(ATTR_TITLE))
        except RequestError:
            _LOGGER.exception("Could not send pushover notification")
