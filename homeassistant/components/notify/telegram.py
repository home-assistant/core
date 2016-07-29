"""
Telegram platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telegram/
"""
import io
import logging
import urllib
import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_DATA, BaseNotificationService)
from homeassistant.const import (CONF_API_KEY, CONF_NAME, ATTR_LOCATION,
                                 ATTR_LATITUDE, ATTR_LONGITUDE, CONF_PLATFORM)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-telegram-bot==5.0.0']

ATTR_PHOTO = "photo"
ATTR_CAPTION = "caption"

CONF_CHAT_ID = 'chat_id'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): "telegram",
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_CHAT_ID): cv.string,
})


def get_service(hass, config):
    """Get the Telegram notification service."""
    import telegram

    try:
        chat_id = config.get(CONF_CHAT_ID)
        api_key = config.get(CONF_API_KEY)
        bot = telegram.Bot(token=api_key)
        username = bot.getMe()['username']
        _LOGGER.info("Telegram bot is '%s'.", username)
    except urllib.error.HTTPError:
        _LOGGER.error("Please check your access token.")
        return None

    return TelegramNotificationService(api_key, chat_id)


def load_data(url=None, file=None, username=None, password=None):
    """Load photo/document into ByteIO/File container from a source."""
    try:
        if url is not None:
            # load photo from url
            if username is not None and password is not None:
                req = requests.get(url, auth=(username, password), timeout=15)
            else:
                req = requests.get(url, timeout=15)
            return io.BytesIO(req.content)

        elif file is not None:
            # load photo from file
            return open(file, "rb")
        else:
            _LOGGER.warning("Can't load photo no photo found in params!")

    except (OSError, IOError, requests.exceptions.RequestException):
        _LOGGER.error("Can't load photo into ByteIO")

    return None


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
        data = kwargs.get(ATTR_DATA)

        # exists data for send a photo/location
        if data is not None and ATTR_PHOTO in data:
            photos = data.get(ATTR_PHOTO, None)
            photos = photos if isinstance(photos, list) else [photos]

            for photo_data in photos:
                self.send_photo(photo_data)
            return
        elif data is not None and ATTR_LOCATION in data:
            return self.send_location(data.get(ATTR_LOCATION))

        # send message
        try:
            self.bot.sendMessage(chat_id=self._chat_id,
                                 text=title + "  " + message)
        except telegram.error.TelegramError:
            _LOGGER.exception("Error sending message.")
            return

    def send_photo(self, data):
        """Send a photo."""
        import telegram
        caption = data.pop(ATTR_CAPTION, None)

        # send photo
        try:
            photo = load_data(**data)
            self.bot.sendPhoto(chat_id=self._chat_id,
                               photo=photo, caption=caption)
        except telegram.error.TelegramError:
            _LOGGER.exception("Error sending photo.")
            return

    def send_location(self, gps):
        """Send a location."""
        import telegram
        latitude = float(gps.get(ATTR_LATITUDE, 0.0))
        longitude = float(gps.get(ATTR_LONGITUDE, 0.0))

        # send location
        try:
            self.bot.sendLocation(chat_id=self._chat_id,
                                  latitude=latitude, longitude=longitude)
        except telegram.error.TelegramError:
            _LOGGER.exception("Error sending location.")
            return
