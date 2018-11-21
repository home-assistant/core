"""
Support for Enigma2 set-top boxes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/enigma/
"""
#
# For more details,
# please refer to github at
# https://github.com/cinzas/homeassistant-enigma-player
#
#
# imports and dependecies
import asyncio
from urllib.error import HTTPError, URLError
import urllib.parse
import urllib.request

import voluptuous as vol

from homeassistant.components.enigma import (
    _LOGGER, DEFAULT_NAME, DEFAULT_PASSWORD,
    DEFAULT_PORT, DEFAULT_USERNAME)
from homeassistant.components.notify import (
    ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

# Default value for display (if not passed as argument in data field)
# 20 seconds for timeout
DEFAULT_DISPLAY_TIME = '20'
# Message type
# 0 -> Yes/No
# 1 -> Info
# 2 -> Message
# 3 -> Attention
DEFAULT_MESSAGE_TYPE = '2'

# Get configs
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


<<<<<<< HEAD
<<<<<<< HEAD
async def get_service(hass, config, discovery_info=None):
    """Initialize the enigma notify service."""
=======
def get_service(hass, config, discovery_info=None):
>>>>>>> pylint corrections.
=======
async def get_service(hass, config, discovery_info=None):
    """Initialize the engima notify service."""
>>>>>>> Missing docstring.
    if config.get(CONF_HOST) is not None:
        enigma = EnigmaNotify(config.get(CONF_HOST),
                              config.get(CONF_PORT),
                              config.get(CONF_NAME),
                              config.get(CONF_USERNAME),
                              config.get(CONF_PASSWORD))

        _LOGGER.info("[Enigma Notify] Enigma receiver at host %s initialized",
                     config.get(CONF_HOST))
    return enigma


class EnigmaNotify(BaseNotificationService):
    """Representation of a notification service for Enigma device."""

    def __init__(self, host, port, name, username, password):
        """Initialize the Enigma device."""
        self._host = host
        self._port = port
        self._name = name
        self._username = username
        self._password = password
        # Opener for http connection
        self._opener = False

        # With auth
        if self._password:
            # Handle HTTP Auth
            mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            mgr.add_password(None, self._host+":"+str(self._port),
                             self._username, self._password)
            handler = urllib.request.HTTPBasicAuthHandler(mgr)
            self._opener = urllib.request.build_opener(handler)
            self._opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        else:
            handler = urllib.request.HTTPHandler()
            self._opener = urllib.request.build_opener(handler)
            self._opener.addheaders = [('User-agent', 'Mozilla/5.0')]

    def request_call(self, url):
        """Call web API request."""
        uri = 'http://' + self._host + ":" + str(self._port) + url
        _LOGGER.debug("Enigma: [request_call] - Call request %s ", uri)
        try:
            return self._opener.open(uri, timeout=10).read().decode('UTF8')
        except (HTTPError, URLError, ConnectionRefusedError):
            _LOGGER.exception("Enigma: [request_call] - Error connecting to \
                              remote enigma %s: %s ", self._host,
                              HTTPError.code)
            return False

    @asyncio.coroutine
    def async_send_message(self, message="", **kwargs):
        """Send message."""
        try:
            displaytime = DEFAULT_DISPLAY_TIME
            messagetype = DEFAULT_MESSAGE_TYPE
            data = kwargs.get(ATTR_DATA) or {}
            if data:
                if 'displaytime' in data:
                    displaytime = data['displaytime']
                if 'messagetype' in data:
                    messagetype = data['messagetype']

            _LOGGER.debug("Enigma notify service: [async_send_message] - Sending Message %s \
                          (timeout=%s and type=%s", message, displaytime,
                          messagetype)
            self.request_call('/web/message?text=' +
                              message.replace(" ", "%20") + '&type=' +
                              messagetype + '&timeout=' + displaytime)
        except ImportError:
            _LOGGER.error("Enigma notify service: [Exception raised]")
