"""
Kodi notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.kodi/
"""
import logging
import voluptuous as vol

from homeassistant.const import (ATTR_ICON, CONF_HOST, CONF_PORT,
                                 CONF_USERNAME, CONF_PASSWORD)
from homeassistant.components.notify import (ATTR_TITLE, ATTR_TITLE_DEFAULT,
                                             ATTR_DATA, PLATFORM_SCHEMA,
                                             BaseNotificationService)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['jsonrpc-requests==0.3']

DEFAULT_PORT = 8080

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Inclusive(CONF_USERNAME, 'auth'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'auth'): cv.string,
})

ATTR_DISPLAYTIME = 'displaytime'


def get_service(hass, config, discovery_info=None):
    """Return the notify service."""
    url = '{}:{}'.format(config.get(CONF_HOST), config.get(CONF_PORT))

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if username is not None:
        auth = (username, password)
    else:
        auth = None

    return KODINotificationService(
        url,
        auth
    )


class KODINotificationService(BaseNotificationService):
    """Implement the notification service for Kodi."""

    def __init__(self, url, auth=None):
        """Initialize the service."""
        import jsonrpc_requests
        self._url = url

        kwargs = {'timeout': 5}

        if auth is not None:
            kwargs['auth'] = auth

        self._server = jsonrpc_requests.Server(
            '{}/jsonrpc'.format(self._url), **kwargs)

    def send_message(self, message="", **kwargs):
        """Send a message to Kodi."""
        import jsonrpc_requests
        try:
            data = kwargs.get(ATTR_DATA) or {}

            displaytime = data.get(ATTR_DISPLAYTIME, 10000)
            icon = data.get(ATTR_ICON, "info")
            title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
            self._server.GUI.ShowNotification(title, message, icon,
                                              displaytime)

        except jsonrpc_requests.jsonrpc.TransportError:
            _LOGGER.warning('Unable to fetch Kodi data, Is Kodi online?')
