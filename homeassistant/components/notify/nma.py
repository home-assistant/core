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
Enter the API for NMA. Go to https://www.notifymyandroid.com and create a
new API to use with Home Assistant.

"""
import logging

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """ Get the NMA notification service. """

    if not validate_config(config,
                           {DOMAIN: [CONF_API_KEY]},
                           _LOGGER):
        return None

    try:
        # pylint: disable=unused-variable
        from homeassistant.external.pynma.pynma import PyNMA

    except ImportError:
        _LOGGER.exception(
            "Unable to import pyNMA. "
            "Did you maybe not install the 'PyNMA' package?")

        return None


# pylint: disable=too-few-public-methods
class NmaNotificationService(BaseNotificationService):
    """ Implements notification service for NMA. """

    def __init__(self, api_key):
        from homeassistant.external.pynma.pynma import PyNMA

        self.nma = PyNMA(api_key)

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        self.nma.push('home-assistant', title, message)
