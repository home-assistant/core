"""
Telstra API platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telstra/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    BaseNotificationService,
    PLATFORM_SCHEMA
)
from homeassistant.const import (CONF_RESOURCE, CONF_METHOD, CONF_NAME)
import homeassistant.helpers.config_validation as cv

CONF_CONSUMER_KEY = 'consumer_key'
CONF_CONSUMER_SECRET = 'consumer_secret'
CONF_PHONE_NUMBER = 'phone_number'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CONSUMER_KEY): cv.string,
    vol.Required(CONF_CONSUMER_SECRET): cv.string,
    vol.Required(CONF_PHONE_NUMBER): cv.string,
})

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the Telstra API notification service."""
    consumer_key = config.get(CONF_CONSUMER_KEY)
    consumer_secret = config.get(CONF_CONSUMER_SECRET)
    phone_number = config.get(CONF_PHONE_NUMBER)

    return TelstraNotificationService(consumer_key,
                                      consumer_secret,
                                      phone_number)


# pylint: disable=too-few-public-methods, too-many-arguments
class TelstraNotificationService(BaseNotificationService):
    """Implementation of a notification service for REST."""

    def __init__(self, consumer_key, consumer_secret, phone_number):
        """Initialize the service."""
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._phone_number = phone_number

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        """Retrieve authorization first"""
        token_data = {
            'client_id': self._consumer_key,
            'client_secret': self._consumer_secret,
            'grant_type': 'client_credentials',
            'scope': 'SMS'
        }
        token_resource = 'https://api.telstra.com/v1/oauth/token'
        token_response = requests.get(token_resource, params=token_data).json()

        if 'error' in token_response:
            _LOGGER.exception('Error obtaining authorization from Telstra API.')
            return

        token = token_response['access_token']

        """Send the SMS"""
        message_data = {
            'to': self._phone_number,
            'body': message
        }
        message_resource = 'https://api.telstra.com/v1/sms/messages'
        message_headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token_response['access_token']
        }
        message_response = requests.post(message_resource,
                                         headers=message_headers,
                                         json=message_data)

        if message_response.status_code != 202:
            _LOGGER.exception(
                "Failed to send SMS. Status code: %d", response.status_code)
