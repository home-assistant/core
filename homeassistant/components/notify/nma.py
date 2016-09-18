"""
NMA (Notify My Android) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.nma/
"""
import logging
import xml.etree.ElementTree as ET

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://www.notifymyandroid.com/publicapi/'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
})


def get_service(hass, config):
    """Get the NMA notification service."""
    response = requests.get(_RESOURCE + 'verify',
                            params={"apikey": config[CONF_API_KEY]})
    tree = ET.fromstring(response.content)

    if tree[0].tag == 'error':
        _LOGGER.error("Wrong API key supplied. %s", tree[0].text)
        return None

    return NmaNotificationService(config[CONF_API_KEY])


# pylint: disable=too-few-public-methods
class NmaNotificationService(BaseNotificationService):
    """Implement the notification service for NMA."""

    def __init__(self, api_key):
        """Initialize the service."""
        self._api_key = api_key

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {
            "apikey": self._api_key,
            "application": 'home-assistant',
            "event": kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
            "description": message,
            "priority": 0,
        }

        response = requests.get(_RESOURCE + 'notify', params=data)
        tree = ET.fromstring(response.content)

        if tree[0].tag == 'error':
            _LOGGER.exception(
                "Unable to perform request. Error: %s", tree[0].text)
