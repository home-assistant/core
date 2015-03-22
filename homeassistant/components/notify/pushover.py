"""
Pushover platform for notify component.

Configuration:

To use the Pushover notifier you will need to add something like the following
to your config/configuration.yaml

notify:
    platform: pushover
    user_key: ABCDEFGHJKLMNOPQRSTUVXYZ

VARIABLES:

user_key
*Required
To retrieve this value log into your account at http://pushover.com

"""
import logging

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

_API_TOKEN = 'a99PmRoFWhchykrsS6MQwgM3mPdhEv'

def get_service(hass, config):
    """ Get the pushover notification service. """

    if not validate_config(config,
                           {DOMAIN: ['user_key']},
                           _LOGGER):
        return None

    try:
        # pylint: disable=unused-variable
        from pushover import Client

    except ImportError:
        _LOGGER.exception(
            "Unable to import pushover. "
            "Did you maybe not install the 'python-pushover.py' package?")

        return None

    try:
        return PushoverNotificationService(config[DOMAIN]['user_key'])

    except InvalidKeyError:
        _LOGGER.error(
            "Wrong API key supplied. "
            "Get it at https://www.pushover.com")


# pylint: disable=too-few-public-methods
class PushoverNotificationService(BaseNotificationService):
    """ Implements notification service for Pushover. """

    def __init__(self, user_key):
        from pushover import Client
        self.user_key = user_key
        self.pushover = client = Client(self.user_key, api_token=_API_TOKEN)

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        self.pushover.send_message(message, title=title)
