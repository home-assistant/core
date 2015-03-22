"""
Pushover platform for notify component.

Configuration:

To use the Pushover notifier you will need to add something like the following
to your config/configuration.yaml

notify:
    platform: pushover
    api_key: ABCDEFGHJKLMNOPQRSTUVXYZ
    user_key: ABCDEFGHJKLMNOPQRSTUVXYZ

VARIABLES:

api_key
*Required
This parameter is optional but should be configured, in order to get an API
key you should go to https://pushover.net and register a new application.

This is a quote from the pushover website regarding free/open source apps:
"If you are creating a client-side library, application, or open source project
that will be redistributed and installed by end-users, you may want to require
each of your users to register their own application rather than including your
own API token with the software."

When setting up the application I recommend using the icon located here:
https://home-assistant.io/images/favicon-192x192.png

user_key
*Required
To retrieve this value log into your account at https://pushover.net

"""
import logging

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-variable
def get_service(hass, config):
    """ Get the pushover notification service. """

    if not validate_config(config,
                           {DOMAIN: ['user_key', CONF_API_KEY]},
                           _LOGGER):
        return None

    try:
        # pylint: disable=no-name-in-module, unused-variable
        from pushover import InitError

    except ImportError:
        _LOGGER.exception(
            "Unable to import pushover. "
            "Did you maybe not install the 'python-pushover.py' package?")

        return None

    try:
        api_token = config[DOMAIN].get(CONF_API_KEY)
        return PushoverNotificationService(
            config[DOMAIN]['user_key'],
            api_token)

    except InitError:
        _LOGGER.error(
            "Wrong API key supplied. "
            "Get it at https://pushover.net")


# pylint: disable=too-few-public-methods
class PushoverNotificationService(BaseNotificationService):
    """ Implements notification service for Pushover. """

    def __init__(self, user_key, api_token):
        # pylint: disable=no-name-in-module, unused-variable
        from pushover import Client
        self._user_key = user_key
        self._api_token = api_token
        self.pushover = Client(
            self._user_key, api_token=self._api_token)

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        # pylint: disable=no-name-in-module
        from pushover import RequestError
        title = kwargs.get(ATTR_TITLE)
        try:
            self.pushover.send_message(message, title=title)
        except RequestError:
            _LOGGER.exception("Could not send pushover notification")
