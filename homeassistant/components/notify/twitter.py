"""
Twitter platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.twitter/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (PLATFORM_SCHEMA,
                                             BaseNotificationService)
from homeassistant.const import CONF_ACCESS_TOKEN

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['TwitterAPI==2.4.2']

CONF_CONSUMER_KEY = "consumer_key"
CONF_CONSUMER_SECRET = "consumer_secret"
CONF_ACCESS_TOKEN_SECRET = "access_token_secret"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CONSUMER_KEY): cv.string,
    vol.Required(CONF_CONSUMER_SECRET): cv.string,
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_ACCESS_TOKEN_SECRET): cv.string,
})


def get_service(hass, config):
    """Get the Twitter notification service."""
    return TwitterNotificationService(config[CONF_CONSUMER_KEY],
                                      config[CONF_CONSUMER_SECRET],
                                      config[CONF_ACCESS_TOKEN],
                                      config[CONF_ACCESS_TOKEN_SECRET])


# pylint: disable=too-few-public-methods
class TwitterNotificationService(BaseNotificationService):
    """Implement notification service for the Twitter service."""

    def __init__(self, consumer_key, consumer_secret, access_token_key,
                 access_token_secret):
        """Initialize the service."""
        from TwitterAPI import TwitterAPI
        self.api = TwitterAPI(consumer_key, consumer_secret, access_token_key,
                              access_token_secret)

    def send_message(self, message="", **kwargs):
        """Tweet some message."""
        resp = self.api.request('statuses/update', {'status': message})
        if resp.status_code != 200:
            import json
            obj = json.loads(resp.text)
            error_message = obj['errors'][0]['message']
            error_code = obj['errors'][0]['code']
            _LOGGER.error("Error %s : %s (Code %s)", resp.status_code,
                          error_message,
                          error_code)
