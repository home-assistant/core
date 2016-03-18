"""
Pushetta platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushetta/
"""
import logging

from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pushetta==1.0.15']


def get_service(hass, config):
    """Get the Pushetta notification service."""
    from pushetta import Pushetta, exceptions

    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_API_KEY, 'channel_name']},
                           _LOGGER):
        return None

    try:
        pushetta = Pushetta(config[CONF_API_KEY])
        pushetta.pushMessage(config['channel_name'], "Home Assistant started")
    except exceptions.TokenValidationError:
        _LOGGER.error("Please check your access token")
        return None
    except exceptions.ChannelNotFoundError:
        _LOGGER.error("Channel '%s' not found", config['channel_name'])
        return None

    return PushettaNotificationService(config[CONF_API_KEY],
                                       config['channel_name'])


# pylint: disable=too-few-public-methods
class PushettaNotificationService(BaseNotificationService):
    """Implement the notification service for Pushetta."""

    def __init__(self, api_key, channel_name):
        """Initialize the service."""
        from pushetta import Pushetta
        self._api_key = api_key
        self._channel_name = channel_name
        self.pushetta = Pushetta(self._api_key)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        title = kwargs.get(ATTR_TITLE)
        self.pushetta.pushMessage(self._channel_name,
                                  "{} {}".format(title, message))
