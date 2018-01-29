"""
clicksend_tts platform for notify component.

This platform sends text to speech audio messages through clicksend

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.clicksend_tts/
"""
import json
import logging

from aiohttp.hdrs import CONTENT_TYPE
import requests
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_API_KEY, CONF_USERNAME, CONF_RECIPIENT, CONTENT_TYPE_JSON)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

BASE_API_URL = 'https://rest.clicksend.com/v3'

HEADERS = {CONTENT_TYPE: CONTENT_TYPE_JSON}

CONF_LANGUAGE = 'language'
CONF_VOICE = 'voice'

DEFAULT_LANGUAGE = 'en-us'
DEFAULT_VOICE = 'female'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
    vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): cv.string,
    vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the ClickSend notification service."""
    if _authenticate(config) is False:
        _LOGGER.error("You are not authorized to access ClickSend")
        return None

    return ClicksendNotificationService(config)


class ClicksendNotificationService(BaseNotificationService):
    """Implementation of a notification service for the ClickSend service."""

    def __init__(self, config):
        """Initialize the service."""
        self.username = config.get(CONF_USERNAME)
        self.api_key = config.get(CONF_API_KEY)
        self.recipient = config.get(CONF_RECIPIENT)
        self.language = config.get(CONF_LANGUAGE)
        self.voice = config.get(CONF_VOICE)

    def send_message(self, message="", **kwargs):
        """Send a voice call to a user."""
        data = ({'messages': [{'source': 'hass.notify', 'from': self.recipient,
                               'to': self.recipient, 'body': message,
                               'lang': self.language, 'voice': self.voice}]})
        api_url = "{}/voice/send".format(BASE_API_URL)
        resp = requests.post(api_url, data=json.dumps(data), headers=HEADERS,
                             auth=(self.username, self.api_key), timeout=5)

        obj = json.loads(resp.text)
        response_msg = obj['response_msg']
        response_code = obj['response_code']
        if resp.status_code != 200:
            _LOGGER.error("Error %s : %s (Code %s)", resp.status_code,
                          response_msg, response_code)


def _authenticate(config):
    """Authenticate with ClickSend."""
    api_url = '{}/account'.format(BASE_API_URL)
    resp = requests.get(api_url, headers=HEADERS,
                        auth=(config.get(CONF_USERNAME),
                              config.get(CONF_API_KEY)), timeout=5)

    if resp.status_code != 200:
        return False

    return True
