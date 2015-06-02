"""
homeassistant.components.notify.nma
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

NMA (Notify My Android) notification service.

Configuration:

To use the NMA notifier you will need to add something like the following
to your config/configuration.yaml

notify:
  platform: nma
  api_key: YOUR_API_KEY

VARIABLES:

api_key
*Required
Enter the API key for NMA. Go to https://www.notifymyandroid.com and create a
new API key to use with Home Assistant.

Details for the API : https://www.notifymyandroid.com/api.jsp

"""
import logging
import xml.etree.ElementTree as ET

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://www.notifymyandroid.com/publicapi/'


def get_service(hass, config):
    """ Get the NMA notification service. """

    if not validate_config(config,
                           {DOMAIN: [CONF_API_KEY]},
                           _LOGGER):
        return None

    try:
        # pylint: disable=unused-variable
        from requests import Session

    except ImportError:
        _LOGGER.exception(
            "Unable to import requests. "
            "Did you maybe not install the 'Requests' package?")

        return None

    nma = Session()
    response = nma.get(_RESOURCE + 'verify',
                       params={"apikey": config[DOMAIN][CONF_API_KEY]})
    tree = ET.fromstring(response.content)

    if tree[0].tag == 'error':
        _LOGGER.error("Wrong API key supplied. %s", tree[0].text)
    else:
        return NmaNotificationService(config[DOMAIN][CONF_API_KEY])


# pylint: disable=too-few-public-methods
class NmaNotificationService(BaseNotificationService):
    """ Implements notification service for NMA. """

    def __init__(self, api_key):
        # pylint: disable=no-name-in-module, unused-variable
        from requests import Session

        self._api_key = api_key
        self._data = {"apikey": self._api_key}

        self.nma = Session()

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        self._data['application'] = 'home-assistant'
        self._data['event'] = title
        self._data['description'] = message
        self._data['priority'] = 0

        response = self.nma.get(_RESOURCE + 'notify',
                                params=self._data)
        tree = ET.fromstring(response.content)

        if tree[0].tag == 'error':
            _LOGGER.exception(
                "Unable to perform request. Error: %s", tree[0].text)
