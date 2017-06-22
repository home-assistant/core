"""
Clicksend platform for notify component.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.clicksend/
"""

# Import dependencies.
import logging
import requests
import json
import base64

import voluptuous as vol

from homeassistant.const import (CONF_USERNAME, CONF_API_KEY, CONF_RECIPIENT,
    HTTP_HEADER_CONTENT_TYPE, CONTENT_TYPE_JSON, HTTP_BASIC_AUTHENTICATION)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)

# Get logger instance.
_LOGGER = logging.getLogger(__name__)

# Set platform  parameters.
BASE_API_URL = 'https://rest.clicksend.com/v3'

# Validate parameter schema.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the ClickSend notification service."""
    if _authenticate(config) is False:
        _LOGGER.exception("You are not authorized to access ClickSend.")
        return None

    return ClicksendNotificationService(config)


class ClicksendNotificationService(BaseNotificationService):
    """Implementation of a notification service for the ClickSend service."""

    def __init__(self, config):
        """Initialize the service."""
        self.username = config.get(CONF_USERNAME)
        self.api_key = config.get(CONF_API_KEY)
        self.recipient = config.get(CONF_RECIPIENT)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = ({'messages': [{'source': 'hass.notify', 'from': self.recipient,
                'to': self.recipient, 'body': message}]})

        headers = {HTTP_HEADER_CONTENT_TYPE: CONTENT_TYPE_JSON}

        api_url = "{}/sms/send".format(BASE_API_URL)

        resp = requests.post(api_url, data=json.dumps(data), headers=headers,
                            auth=(self.username, self.api_key), timeout=5)

        obj = json.loads(resp.text)
        response_msg = obj['response_msg']
        response_code = obj['response_code']

        # Display error when failed.
        if resp.status_code != 200:
            _LOGGER.error("Error %s : %s (Code %s)", resp.status_code,
                          response_msg, response_code)


def _authenticate(config):
    """Authenticate with ClickSend."""
    api_url = '{}/account'.format(BASE_API_URL)
    headers = {HTTP_HEADER_CONTENT_TYPE: CONTENT_TYPE_JSON}

    resp = requests.get(api_url, auth=(config.get(CONF_USERNAME),
                        config.get(CONF_API_KEY)), timeout=5)

    if resp.status_code != 200:
        return False

    return True
