"""
Pushsafer platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushsafer/
"""
import logging
import base64
import mimetypes
import requests
from requests.auth import HTTPBasicAuth
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_TARGET, ATTR_DATA,
    PLATFORM_SCHEMA, BaseNotificationService)
import homeassistant.helpers.config_validation as cv
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
ATTR_PICTURE1 = 'picture1'

ATTR_SOUND_DEFAULT = ''
ATTR_VIBRATION_DEFAULT = ''
ATTR_ICON_DEFAULT = ''
ATTR_ICONCOLOR_DEFAULT = ''
ATTR_URL_DEFAULT = ''
ATTR_URLTITLE_DEFAULT = ''
ATTR_TIME2LIVE_DEFAULT = ''
ATTR_PICTURE1_DEFAULT = ''

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
        """Send a message to a device."""
        _LOGGER.info("Sending message")

        """Send a message to specified target.
        If no target specified (group or device),
        a push will be sent to all devices
        parameter d for devices is ignored here
        """
        if kwargs.get(ATTR_TARGET) is None:
            targets = ["a"]
            _LOGGER.debug("No target specified. Sending push to all")
        else:
            targets = kwargs.get(ATTR_TARGET)
            _LOGGER.debug("%s target(s) specified", len(targets))

        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA)

        if data is None:
            data = {}
        """ Converting the specified image to base64"""
        picture1 = data.get(ATTR_PICTURE1)
        picture1_encoded = ""
        if picture1 is not None:
            picture1_encoded = self.loadfromfile(
                url=picture1.get(ATTR_PICTURE1_URL),
                local_path=picture1.get(ATTR_PICTURE1_PATH),
                username=picture1.get(ATTR_PICTURE1_USERNAME),
                password=picture1.get(ATTR_PICTURE1_PASSWORD),
                auth=picture1.get(ATTR_PICTURE1_AUTH))
            # _LOGGER.debug("Base64: %s", picture1_encoded)

        payload = {
            'k': self._private_key,
            't': title,
            'm': message,
            's': data.get(ATTR_SOUND, ATTR_SOUND_DEFAULT),
            'v': data.get(ATTR_VIBRATION, ATTR_VIBRATION_DEFAULT),
            'i': data.get(ATTR_ICON, ATTR_ICON_DEFAULT),
            'c': data.get(ATTR_ICONCOLOR, ATTR_ICONCOLOR_DEFAULT),
            'u': data.get(ATTR_URL, ATTR_URL_DEFAULT),
            'ut': data.get(ATTR_URLTITLE, ATTR_URLTITLE_DEFAULT),
            'l': data.get(ATTR_TIME2LIVE, ATTR_TIME2LIVE_DEFAULT),
            'p': picture1_encoded
        }

        _LOGGER.debug("using push data: %s", str(payload))

        for target in targets:
            """ Adding/Overwriting device target to payload"""
            payload['d'] = target
            response = requests.post(_RESOURCE, data=payload,
                                     timeout=CONF_TIMEOUT)
            if response.status_code != '200':
                _LOGGER.error("Pushsafer failed with: %s", response.text)
            else:
                _LOGGER.debug("Push send: %s", response.json())
                
    def convertbase64string(self, filebyte, mimetype):
        """Convert the image to the expected base64 string of pushsafer."""
        _LOGGER.debug("Base64 got mimetype: %s", mimetype)
        if mimetype in _ALLOWED_IMAGES:
            if filebyte is not None:
                base64_image = base64.b64encode(filebyte).decode('utf8')
                _LOGGER.debug("Base64 encoded image: %s", base64_image)
                return "data:"+mimetype+";base64,"+base64_image
            else:
                _LOGGER.warning("Base64 encode no image passed")
        else:
            _LOGGER.warning("%s is a not supported mimetype for images",
                            mimetype)
            return None

    def loadfromfile(self, url=None, local_path=None, username=None,
                       password=None, auth=None):
        """Load image/document/etc from a local path or URL."""
        try:
            if url is not None:
                _LOGGER.debug("Downloading image from %s", url)
                if username is not None and password is not None:
                    auth_ = HTTPBasicAuth(username, password)
                    response = requests.get(url, auth=auth_,
                                            timeout=CONF_TIMEOUT)
                else:
                    response = requests.get(url, timeout=CONF_TIMEOUT)
                    return self.convertbase64string(
                        response.content,
                        response.headers['content-type'])

            elif local_path is not None:
                _LOGGER.debug("Loading image from local path")
                """Check whether path is whitelisted in configuration.yaml """
                if self.is_allowed_path(local_path):
                    file_mimetype = mimetypes.guess_type(local_path)
                    _LOGGER.debug("Detected mimetype %s", file_mimetype)
                    with open(local_path, "rb") as binary_file:
                        data = binary_file.read()
                    return self.convertbase64string(data, file_mimetype[0])
                _LOGGER.warning("'%s' is not secure to load data from!",
                                local_path)
            else:
                _LOGGER.warning("Neither URL nor local path found in params!")

        except OSError as error:
            _LOGGER.error("Can't load from url or local path: %s", error)

        return None
