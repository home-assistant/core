"""
Clicksend platform for notify component.
For more details about this platform, please refer to the documentation at
https://clicksend.com/help
"""

# Import dependencies.
import logging
import requests
import json
import base64

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)

# Get logger instance.
_LOGGER = logging.getLogger(__name__)

# Set platform  parameters.
CONF_API_URL = 'https://rest.clicksend.com/v3/sms/send'
CONF_USERNAME = 'username'
CONF_API_KEY = 'api_key'
CONF_TO_NO = 'to_no'

# Validate parameter schema.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_TO_NO): cv.string,
})

# Define service instance.
def get_service(hass, config, discovery_info=None):

    # Set notification service instance.
    return ClicksendNotificationService(config[CONF_USERNAME], config[CONF_API_KEY], config[CONF_TO_NO])

# Implement the notification service.
class ClicksendNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Twitter service."""

    def __init__(self, username, api_key, to_no):

        # Set variables.
        self.username = username
        self.api_key = api_key
        self.to_no = to_no

    def send_message(self, message="", **kwargs):

        # Send request.
        auth = self.username + ':' + self.api_key
        auth = base64.b64encode(bytes(auth, 'utf-8'))
        auth = 'Basic ' + auth.decode('utf-8')

        data = {'messages': [{'source': 'hass.notify', 'from': self.to_no, 'to': self.to_no, 'body': message}]}
        headers = {'Content-type': 'application/json', 'Authorization': auth}

        resp = requests.post(CONF_API_URL, data=json.dumps(data), headers=headers)

        obj = json.loads(resp.text)
        response_msg = obj['response_msg']
        response_code = obj['response_code']

        # Display error when failed.
        if resp.status_code != 200:
            _LOGGER.error("Error %s : %s (Code %s)", resp.status_code,
                          response_msg, response_code)