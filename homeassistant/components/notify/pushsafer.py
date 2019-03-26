"""
Pushsafer platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushsafer/
"""
import base64
import logging
import mimetypes

import requests
from requests.auth import HTTPBasicAuth
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from . import (
    ATTR_DATA, ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA,
    BaseNotificationService)

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://www.pushsafer.com/api'
_ALLOWED_IMAGES = ['image/gif', 'image/jpeg', 'image/png']

CONF_DEVICE_KEY = 'private_key'
CONF_TIMEOUT = 15

# Top level attributes in 'data'
ATTR_SOUND = 'sound'
ATTR_VIBRATION = 'vibration'
ATTR_ICON = 'icon'
ATTR_ICONCOLOR = 'iconcolor'
ATTR_URL = 'url'
ATTR_URLTITLE = 'urltitle'
ATTR_TIME2LIVE = 'time2live'
ATTR_PRIORITY = 'priority'
ATTR_RETRY = 'retry'
ATTR_EXPIRE = 'expire'
ATTR_ANSWER = 'answer'
ATTR_PICTURE1 = 'picture1'

# Attributes contained in picture1
ATTR_PICTURE1_URL = 'url'
ATTR_PICTURE1_PATH = 'path'
ATTR_PICTURE1_USERNAME = 'username'
ATTR_PICTURE1_PASSWORD = 'password'
ATTR_PICTURE1_AUTH = 'auth'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_KEY): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Pushsafer.com notification service."""
    return PushsaferNotificationService(config.get(CONF_DEVICE_KEY),
                                        hass.config.is_allowed_path)


class PushsaferNotificationService(BaseNotificationService):
    """Implementation of the notification service for Pushsafer.com."""

    def __init__(self, private_key, is_allowed_path):
        """Initialize the service."""
        self._private_key = private_key
        self.is_allowed_path = is_allowed_path

    def send_message(self, message='', **kwargs):
        """Send a message to specified target."""
        if kwargs.get(ATTR_TARGET) is None:
            targets = ["a"]
            _LOGGER.debug("No target specified. Sending push to all")
        else:
            targets = kwargs.get(ATTR_TARGET)
            _LOGGER.debug("%s target(s) specified", len(targets))

        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA, {})

        # Converting the specified image to base64
        picture1 = data.get(ATTR_PICTURE1)
        picture1_encoded = ""
        if picture1 is not None:
            _LOGGER.debug("picture1 is available")
            url = picture1.get(ATTR_PICTURE1_URL, None)
            local_path = picture1.get(ATTR_PICTURE1_PATH, None)
            username = picture1.get(ATTR_PICTURE1_USERNAME)
            password = picture1.get(ATTR_PICTURE1_PASSWORD)
            auth = picture1.get(ATTR_PICTURE1_AUTH)

            if url is not None:
                _LOGGER.debug("Loading image from url %s", url)
                picture1_encoded = self.load_from_url(url, username,
                                                      password, auth)
            elif local_path is not None:
                _LOGGER.debug("Loading image from file %s", local_path)
                picture1_encoded = self.load_from_file(local_path)
            else:
                _LOGGER.warning("missing url or local_path for picture1")
        else:
            _LOGGER.debug("picture1 is not specified")

        payload = {
            'k': self._private_key,
            't': title,
            'm': message,
            's': data.get(ATTR_SOUND, ""),
            'v': data.get(ATTR_VIBRATION, ""),
            'i': data.get(ATTR_ICON, ""),
            'c': data.get(ATTR_ICONCOLOR, ""),
            'u': data.get(ATTR_URL, ""),
            'ut': data.get(ATTR_URLTITLE, ""),
            'l': data.get(ATTR_TIME2LIVE, ""),
            'pr': data.get(ATTR_PRIORITY, ""),
            're': data.get(ATTR_RETRY, ""),
            'ex': data.get(ATTR_EXPIRE, ""),
            'a': data.get(ATTR_ANSWER, ""),
            'p': picture1_encoded
        }

        for target in targets:
            payload['d'] = target
            response = requests.post(_RESOURCE, data=payload,
                                     timeout=CONF_TIMEOUT)
            if response.status_code != 200:
                _LOGGER.error("Pushsafer failed with: %s", response.text)
            else:
                _LOGGER.debug("Push send: %s", response.json())

    @classmethod
    def get_base64(cls, filebyte, mimetype):
        """Convert the image to the expected base64 string of pushsafer."""
        if mimetype not in _ALLOWED_IMAGES:
            _LOGGER.warning("%s is a not supported mimetype for images",
                            mimetype)
            return None

        base64_image = base64.b64encode(filebyte).decode('utf8')
        return "data:{};base64,{}".format(mimetype, base64_image)

    def load_from_url(self, url=None, username=None, password=None, auth=None):
        """Load image/document/etc from URL."""
        if url is not None:
            _LOGGER.debug("Downloading image from %s", url)
            if username is not None and password is not None:
                auth_ = HTTPBasicAuth(username, password)
                response = requests.get(url, auth=auth_,
                                        timeout=CONF_TIMEOUT)
            else:
                response = requests.get(url, timeout=CONF_TIMEOUT)
            return self.get_base64(response.content,
                                   response.headers['content-type'])
        _LOGGER.warning("url not found in param")

        return None

    def load_from_file(self, local_path=None):
        """Load image/document/etc from a local path."""
        try:
            if local_path is not None:
                _LOGGER.debug("Loading image from local path")
                if self.is_allowed_path(local_path):
                    file_mimetype = mimetypes.guess_type(local_path)
                    _LOGGER.debug("Detected mimetype %s", file_mimetype)
                    with open(local_path, "rb") as binary_file:
                        data = binary_file.read()
                    return self.get_base64(data, file_mimetype[0])
            else:
                _LOGGER.warning("Local path not found in params!")
        except OSError as error:
            _LOGGER.error("Can't load from local path: %s", error)

        return None
