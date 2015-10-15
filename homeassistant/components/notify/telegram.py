"""
homeassistant.components.notify.telegram
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Telegram platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telegram.html
"""
import logging
import urllib

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['python-telegram-bot==2.8.7']


def get_service(hass, config):
    """ Get the Telegram notification service. """

    if not validate_config(config,
                           {DOMAIN: [CONF_API_KEY, 'chat_id']},
                           _LOGGER):
        return None

    try:
        import telegram
    except ImportError:
        _LOGGER.exception(
            "Unable to import python-telegram-bot. "
            "Did you maybe not install the 'python-telegram-bot' package?")
        return None

    try:
        bot = telegram.Bot(token=config[DOMAIN][CONF_API_KEY])
        username = bot.getMe()['username']
        _LOGGER.info("Telegram bot is' %s'", username)
    except urllib.error.HTTPError:
        _LOGGER.error("Please check your access token.")
        return None

    return TelegramNotificationService(
        config[DOMAIN][CONF_API_KEY],
        config[DOMAIN]['chat_id'])


# pylint: disable=too-few-public-methods
class TelegramNotificationService(BaseNotificationService):
    """ Implements notification service for Telegram. """

    def __init__(self, api_key, chat_id):
        import telegram
        self._api_key = api_key
        self._chat_id = chat_id
        self.bot = telegram.Bot(token=self._api_key)

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        self.bot.sendMessage(chat_id=self._chat_id,
                             text=title + "  " + message)
