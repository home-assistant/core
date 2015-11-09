"""
homeassistant.components.notify.pushbullet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
PushBullet platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushbullet.html
"""
import logging

from homeassistant.components.notify import ATTR_TITLE, BaseNotificationService
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pushbullet.py==0.8.1']


def get_service(hass, config):
    """ Get the PushBullet notification service. """
    from pushbullet import InvalidKeyError

    if CONF_API_KEY not in config:
        _LOGGER.error("Unable to find config key '%s'", CONF_API_KEY)
        return None

    try:
        return PushBulletNotificationService(config[CONF_API_KEY])

    except InvalidKeyError:
        _LOGGER.error(
            "Wrong API key supplied. "
            "Get it at https://www.pushbullet.com/account")
        return None


# pylint: disable=too-few-public-methods
class PushBulletNotificationService(BaseNotificationService):
    """ Implements notification service for Pushbullet. """

    def __init__(self, api_key):
        from pushbullet import Pushbullet

        self.pushbullet = Pushbullet(api_key)

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        self.pushbullet.push_note(title, message)
