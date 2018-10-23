"""
Clicksend platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.clicksend/
"""
import json
import logging

from aiohttp.hdrs import CONTENT_TYPE
import requests
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_API_KEY, CONF_RECIPIENT, CONF_SENDER, CONF_USERNAME,
    CONTENT_TYPE_JSON)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

BASE_API_URL = 'https://rest.clicksend.com/v3'

DEFAULT_SENDER = 'hass'

HEADERS = {CONTENT_TYPE: CONTENT_TYPE_JSON}


def validate_sender(config):
    """Set the optional sender name if sender name is not provided."""
    if CONF_SENDER in config:
        return config
    config[CONF_SENDER] = DEFAULT_SENDER
    return config


PLATFORM_SCHEMA = vol.Schema(
    vol.All(PLATFORM_SCHEMA.extend({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_RECIPIENT, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_SENDER): cv.string,
    }), validate_sender))


def get_service(hass, config, discovery_info=None):
    """Get the ClickSend notification service."""
    print("#### ", config)
    if _authenticate(config) is False:
        _LOGGER.exception("You are not authorized to access ClickSend")
        return None

    return ClicksendNotificationService(config)


class ClicksendNotificationService(BaseNotificationService):
    """Implementation of a notification service for the ClickSend service."""

    def __init__(self, config):
        """Initialize the service."""
        self.username = config.get(CONF_USERNAME)
        self.api_key = config.get(CONF_API_KEY)
        self.recipients = config.get(CONF_RECIPIENT)
        self.sender = config.get(CONF_SENDER)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {"messages": []}
        for recipient in self.recipients:
            data["messages"].append({
                'source': 'hass.notify',
                'from': self.sender,
                'to': recipient,
                'body': message,
            })

        api_url = "{}/sms/send".format(BASE_API_URL)

        resp = requests.post(
            api_url, data=json.dumps(data), headers=HEADERS,
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
    resp = requests.get(
        api_url, headers=HEADERS, auth=(config.get(CONF_USERNAME),
                                        config.get(CONF_API_KEY)), timeout=5)

    if resp.status_code != 200:
        return False

    return True
