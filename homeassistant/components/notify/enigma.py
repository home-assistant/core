"""Support for Enigma2 notifications."""
#
# For more details,
# please refer to github at
# https://github.com/cinzas/homeassistant-enigma-player
#
#
# imports and dependecies
import logging
import urllib.request
import urllib.parse
from urllib.error import URLError, HTTPError
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.components.notify import (
    ATTR_DATA, PLATFORM_SCHEMA,
    BaseNotificationService)

# Logging
_LOGGER = logging.getLogger(__name__)

# Default values
DEFAULT_PORT = 80
DEFAULT_NAME = 'dreambox'
DEFAULT_USERNAME = 'root'
DEFAULT_PASSWORD = None

# Default value for display (if not passed as argument in data field)
# 20 seconds for timeout
DISPLAY_TIME = '20'
# Message type
# 0 -> Yes/No
# 1 -> Info
# 2 -> Message
# 3 -> Attention
MESSAGE_TYPE = '2'

# Get configs
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


async def async_get_service(hass, config, discovery_info=None):
    """Return the notify service."""
    if config.get(CONF_HOST) is not None:
        enigma = EnigmaNotify(config.get(CONF_NAME),
                              config.get(CONF_HOST),
                              config.get(CONF_PORT),
                              config.get(CONF_USERNAME),
                              config.get(CONF_PASSWORD))

        _LOGGER.info("[Enigma Notify] Enigma receiver at host %s initialized",
                     config.get(CONF_HOST))
    return enigma


class EnigmaNotify(BaseNotificationService):
    """Representation of a notification service for Enigma device."""

    def __init__(self, name, host, port, username, password):
        """Initialize the Enigma device."""
        self._name = name
        self._host = host
        self._port = port
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
            displaytime = DISPLAY_TIME
            messagetype = MESSAGE_TYPE
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
