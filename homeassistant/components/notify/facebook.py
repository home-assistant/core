"""
Facebook platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.facebook/
"""
import logging

import requests

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

CONF_ID = 'id'
CONF_PHONE_NUMBER = 'phone_number'
CONF_PAGE_ACCESS_TOKEN = 'page_access_token'
BASE_URL = 'https://graph.facebook.com/v2.6/me/messages'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PHONE_NUMBER): cv.string,
    vol.Required(CONF_PAGE_ACCESS_TOKEN): cv.string,
})


def get_service(hass, config):
    """Get the Twitter notification service."""
    return FacebookNotificationService(
        config[CONF_PHONE_NUMBER], config[CONF_PAGE_ACCESS_TOKEN]
    )


class FacebookNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Twitter service."""

    def __init__(self, id, access_token):
        """Initialize the service."""
        self.user_id = id
        self.page_access_token = access_token

    def send_message(self, message="", **kwargs):
        """Send some message."""
        payload = {'access_token': self.page_access_token}
        body = {
            "recipient": {"phone_number": self.user_id},
            "message": {"text": message}
        }
        import json
        resp = requests.post(BASE_URL, data=json.dumps(body), params=payload,
                             headers={'Content-Type': 'application/json'})
        if resp.status_code != 200:
            obj = resp.json()
            error_message = obj['error']['message']
            error_code = obj['error']['code']
            _LOGGER.error("Error %s : %s (Code %s)", resp.status_code,
                          error_message,
                          error_code)
