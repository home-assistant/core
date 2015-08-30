"""
homeassistant.components.notify.pushbullet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PushBullet platform for notify component.

Configuration:

To use the PushBullet notifier you will need to add something like the
following to your config/configuration.yaml

notify:
  platform: pushbullet
  api_key: YOUR_API_KEY

Variables:

api_key
*Required
Enter the API key for PushBullet. Go to https://www.pushbullet.com/ to retrieve
your API key.
"""
import logging

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pushbullet.py==0.7.1']


def get_service(hass, config):
    """ Get the pushbullet notification service. """

    if not validate_config(config,
                           {DOMAIN: [CONF_API_KEY]},
                           _LOGGER):
        return None

    try:
        # pylint: disable=unused-variable
        from pushbullet import PushBullet, InvalidKeyError  # noqa

    except ImportError:
        _LOGGER.exception(
            "Unable to import pushbullet. "
            "Did you maybe not install the 'pushbullet.py' package?")

        return None

    try:
        return PushBulletNotificationService(config[DOMAIN][CONF_API_KEY])

    except InvalidKeyError:
        _LOGGER.error(
            "Wrong API key supplied. "
            "Get it at https://www.pushbullet.com/account")


# pylint: disable=too-few-public-methods
class PushBulletNotificationService(BaseNotificationService):
    """ Implements notification service for Pushbullet. """

    def __init__(self, api_key):
        from pushbullet import PushBullet

        self.pushbullet = PushBullet(api_key)

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        self.pushbullet.push_note(title, message)
