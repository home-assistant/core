"""
Pushetta platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushetta/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pushetta==1.0.15']


CONF_CHANNEL_NAME = 'channel_name'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_CHANNEL_NAME): cv.string,
})


def get_service(hass, config):
    """Get the Pushetta notification service."""
    from pushetta import Pushetta, exceptions

    try:
        pushetta = Pushetta(config[CONF_API_KEY])
        pushetta.pushMessage(config[CONF_CHANNEL_NAME],
                             "Home Assistant started")
    except exceptions.TokenValidationError:
        _LOGGER.error("Please check your access token")
        return None
    except exceptions.ChannelNotFoundError:
        _LOGGER.error("Channel '%s' not found", config[CONF_CHANNEL_NAME])
        return None

    return PushettaNotificationService(config[CONF_API_KEY],
                                       config[CONF_CHANNEL_NAME])


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
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        self.pushetta.pushMessage(self._channel_name,
                                  "{} {}".format(title, message))
