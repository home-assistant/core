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
CONF_SEND_TEST_MSG = 'send_test_msg'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_CHANNEL_NAME): cv.string,
    vol.Optional(CONF_SEND_TEST_MSG, default=False): cv.boolean,
})


def get_service(hass, config):
    """Get the Pushetta notification service."""
    pushetta_service = PushettaNotificationService(config[CONF_API_KEY],
                                                   config[CONF_CHANNEL_NAME],
                                                   config[CONF_SEND_TEST_MSG])

    if pushetta_service.is_valid:
        return pushetta_service


# pylint: disable=too-few-public-methods
class PushettaNotificationService(BaseNotificationService):
    """Implement the notification service for Pushetta."""

    def __init__(self, api_key, channel_name, send_test_msg):
        """Initialize the service."""
        from pushetta import Pushetta
        self._api_key = api_key
        self._channel_name = channel_name
        self.is_valid = True
        self.pushetta = Pushetta(api_key)

        if send_test_msg:
            self.send_message("Home Assistant started")

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from pushetta import exceptions
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        try:
            self.pushetta.pushMessage(self._channel_name,
                                      "{} {}".format(title, message))
        except exceptions.TokenValidationError:
            _LOGGER.error("Please check your access token")
            self.is_valid = False
        except exceptions.ChannelNotFoundError:
            _LOGGER.error("Channel '%s' not found", self._channel_name)
            self.is_valid = False
