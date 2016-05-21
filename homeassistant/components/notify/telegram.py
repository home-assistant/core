"""
Telegram platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telegram/
"""
import logging
import urllib

from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-telegram-bot==4.1.1']


def get_service(hass, config):
    """Get the Telegram notification service."""
    import telegram

    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_API_KEY, 'chat_id']},
                           _LOGGER):
        return None

    try:
        bot = telegram.Bot(token=config[CONF_API_KEY])
        username = bot.getMe()['username']
        _LOGGER.info("Telegram bot is '%s'.", username)
    except urllib.error.HTTPError:
        _LOGGER.error("Please check your access token.")
        return None

    return TelegramNotificationService(config[CONF_API_KEY], config['chat_id'])


# pylint: disable=too-few-public-methods
class TelegramNotificationService(BaseNotificationService):
    """Implement the notification service for Telegram."""

    def __init__(self, api_key, chat_id):
        """Initialize the service."""
        import telegram

        self._api_key = api_key
        self._chat_id = chat_id
        self.bot = telegram.Bot(token=self._api_key)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        import telegram

        title = kwargs.get(ATTR_TITLE)

        try:
            self.bot.sendMessage(chat_id=self._chat_id,
                                 text=title + "  " + message)
        except telegram.error.TelegramError:
            _LOGGER.exception("Error sending message.")
