"""
Telegram platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telegram/
"""
import logging
import urllib
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_CAPTION, BaseNotificationService)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PLATFORM

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ["python-telegram-bot==5.0.0"]

CONF_CHAT_ID = 'chat_id'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): "telegram",
    vol.Required(CONF_NAME): vol.Coerce(str),
    vol.Required(CONF_API_KEY): vol.Coerce(str),
    vol.Required(CONF_CHAT_ID): vol.Coerce(str),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the Telegram notification service."""
    import telegram

    try:
        api_key = config.get(CONF_API_KEY)
        chat_id = config.get(CONF_CHAT_ID)
        name = config.get(CONF_NAME)
        bot = telegram.Bot(token=api_key)
        username = bot.getMe()['username']
        _LOGGER.info("Telegram bot is '%s'.", username)
    except urllib.error.HTTPError:
        _LOGGER.error("Please check your access token.")
        return False

    add_devices([TelegramNotificationService(api_key, chat_id, name)])


# pylint: disable=too-few-public-methods
class TelegramNotificationService(BaseNotificationService):
    """Implement the notification service for Telegram."""

    def __init__(self, api_key, chat_id, name):
        """Initialize the service."""
        import telegram

        self._api_key = api_key
        self._chat_id = chat_id
        self._name = name
        self.bot = telegram.Bot(token=self._api_key)

    @property
    def name(self):
        """Return name of notification entity."""
        return self._name

    def send_message(self, message, **kwargs):
        """Send a message to a user."""
        import telegram

        title = kwargs.get(ATTR_TITLE)

        # send message
        try:
            self.bot.sendMessage(chat_id=self._chat_id,
                                 text=title + "  " + message)
        except telegram.error.TelegramError:
            _LOGGER.exception("Error sending message.")
            return

    def send_photo(self, photo, **kwargs):
        """Send a photo."""
        import telegram

        data = self.load_photo(**photo)
        if data is None:
            _LOGGER.error("No photo found!")
            return

        try:
            caption = kwargs.get(ATTR_CAPTION, None)
            self.bot.sendPhoto(chat_id=self._chat_id,
                               photo=data, caption=caption)

        except (telegram.error.TelegramError, urllib.error.HTTPError):
            _LOGGER.exception("Error sending photo.")
            return

    def send_location(self, latitude, longitude, **kwargs):
        """Send a location."""
        import telegram
        try:
            self.bot.sendLocation(chat_id=self._chat_id,
                                  latitude=latitude, longitude=longitude)

        except telegram.error.TelegramError:
            _LOGGER.exception("Error sending location.")
            return
