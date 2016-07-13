"""
Telegram platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telegram/
"""
import io
import logging
import urllib
import requests
from requests.auth import HTTPBasicAuth

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_DATA, DOMAIN, BaseNotificationService)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-telegram-bot==4.3.3']

ATTR_PHOTO = "photo"
ATTR_FILE = "file"
ATTR_URL = "url"
ATTR_CAPTION = "caption"
ATTR_USERNAME = "username"
ATTR_PASSWORD = "password"


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
        data = kwargs.get(ATTR_DATA, {})

        # send message
        try:
            self.bot.sendMessage(chat_id=self._chat_id,
                                 text=title + "  " + message)
        except telegram.error.TelegramError:
            _LOGGER.exception("Error sending message.")
            return

        # send photo
        if ATTR_PHOTO in data:
            # if not a list
            if not isinstance(data[ATTR_PHOTO], list):
                photos = [data[ATTR_PHOTO]]
            else:
                photos = data[ATTR_PHOTO]

            try:
                for photo_data in photos:
                    caption = photo_data.get(ATTR_CAPTION, None)

                    # file is a url
                    if ATTR_URL in photo_data:
                        # use http authenticate
                        if ATTR_USERNAME in photo_data and\
                           ATTR_PASSWORD in photo_data:
                            req = requests.get(
                                photo_data[ATTR_URL],
                                auth=HTTPBasicAuth(photo_data[ATTR_USERNAME],
                                                   photo_data[ATTR_PASSWORD])
                            )
                        else:
                            req = requests.get(photo_data[ATTR_URL])
                        file_id = io.BytesIO(req.content)
                    elif ATTR_FILE in photo_data:
                        file_id = open(photo_data[ATTR_FILE], "rb")
                    else:
                        _LOGGER.error("No url or path is set for photo!")
                        continue

                    self.bot.sendPhoto(chat_id=self._chat_id,
                                       photo=file_id, caption=caption)

            except (OSError, IOError, telegram.error.TelegramError,
                    urllib.error.HTTPError):
                _LOGGER.exception("Error sending photo.")
                return
