"""
NMA (Notify My Android) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.nma/
"""
import logging
import xml.etree.ElementTree as ET

import requests

from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://www.notifymyandroid.com/publicapi/'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the NMA notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_API_KEY]},
                           _LOGGER):
        return False

    api_key = config.get(CONF_API_KEY)
    name = config.get(CONF_NAME)
    response = requests.get(_RESOURCE + 'verify',
                            params={"apikey": api_key})
    tree = ET.fromstring(response.content)

    if tree[0].tag == 'error':
        _LOGGER.error("Wrong API key supplied. %s", tree[0].text)
        return False

    add_devices([NmaNotificationService(api_key, name)])


# pylint: disable=too-few-public-methods,abstract-method
class NmaNotificationService(BaseNotificationService):
    """Implement the notification service for NMA."""

    def __init__(self, api_key, name):
        """Initialize the service."""
        self._api_key = api_key
        self._name = name

    @property
    def name(self):
        """Return name of notification entity."""
        return self._name

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {
            "apikey": self._api_key,
            "application": 'home-assistant',
            "event": kwargs.get(ATTR_TITLE),
            "description": message,
            "priority": 0,
        }

        response = requests.get(_RESOURCE + 'notify', params=data)
        tree = ET.fromstring(response.content)

        if tree[0].tag == 'error':
            _LOGGER.exception(
                "Unable to perform request. Error: %s", tree[0].text)
