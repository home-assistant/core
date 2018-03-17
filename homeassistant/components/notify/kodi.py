"""
Kodi notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.kodi/
"""
import asyncio
import logging

import aiohttp
import voluptuous as vol

from homeassistant.const import (
    ATTR_ICON, CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD,
    CONF_PROXY_SSL)
from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_DATA, PLATFORM_SCHEMA,
    BaseNotificationService)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['jsonrpc-async==0.6']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8080
DEFAULT_PROXY_SSL = False
DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_PROXY_SSL, default=DEFAULT_PROXY_SSL): cv.boolean,
    vol.Inclusive(CONF_USERNAME, 'auth'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'auth'): cv.string,
})

ATTR_DISPLAYTIME = 'displaytime'


@asyncio.coroutine
def async_get_service(hass, config, discovery_info=None):
    """Return the notify service."""
    url = '{}:{}'.format(config.get(CONF_HOST), config.get(CONF_PORT))

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    encryption = config.get(CONF_PROXY_SSL)

    if host.startswith('http://') or host.startswith('https://'):
        host = host[host.index('://') + 3:]
        _LOGGER.warning(
            "Kodi host name should no longer contain http:// See updated "
            "definitions here: "
            "https://home-assistant.io/components/media_player.kodi/")

    http_protocol = 'https' if encryption else 'http'
    url = '{}://{}:{}/jsonrpc'.format(http_protocol, host, port)

    if username is not None:
        auth = aiohttp.BasicAuth(username, password)
    else:
        auth = None

    return KodiNotificationService(hass, url, auth)


class KodiNotificationService(BaseNotificationService):
    """Implement the notification service for Kodi."""

    def __init__(self, hass, url, auth=None):
        """Initialize the service."""
        import jsonrpc_async
        self._url = url

        kwargs = {
            'timeout': DEFAULT_TIMEOUT,
            'session': async_get_clientsession(hass),
        }

        if auth is not None:
            kwargs['auth'] = auth

        self._server = jsonrpc_async.Server(self._url, **kwargs)

    @asyncio.coroutine
    def async_send_message(self, message="", **kwargs):
        """Send a message to Kodi."""
        import jsonrpc_async
        try:
            data = kwargs.get(ATTR_DATA) or {}

            displaytime = data.get(ATTR_DISPLAYTIME, 10000)
            icon = data.get(ATTR_ICON, "info")
            title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
            yield from self._server.GUI.ShowNotification(
                title, message, icon, displaytime)

        except jsonrpc_async.TransportError:
            _LOGGER.warning("Unable to fetch Kodi data. Is Kodi online?")
