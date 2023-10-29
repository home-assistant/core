"""Kodi notification service."""
from __future__ import annotations

import logging

import aiohttp
import jsonrpc_async
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import (
    ATTR_ICON,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROXY_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8080
DEFAULT_PROXY_SSL = False
DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PROXY_SSL, default=DEFAULT_PROXY_SSL): cv.boolean,
        vol.Inclusive(CONF_USERNAME, "auth"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "auth"): cv.string,
    }
)

ATTR_DISPLAYTIME = "displaytime"


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> KodiNotificationService:
    """Return the notify service."""
    username: str | None = config.get(CONF_USERNAME)
    password: str | None = config.get(CONF_PASSWORD)

    host: str = config[CONF_HOST]
    port: int = config[CONF_PORT]
    encryption = config.get(CONF_PROXY_SSL)

    if host.startswith("http://") or host.startswith("https://"):
        host = host[host.index("://") + 3 :]
        _LOGGER.warning(
            "Kodi host name should no longer contain http:// See updated "
            "definitions here: "
            "https://www.home-assistant.io/integrations/media_player.kodi/"
        )

    http_protocol = "https" if encryption else "http"
    url = f"{http_protocol}://{host}:{port}/jsonrpc"

    if username is not None and password is not None:
        auth = aiohttp.BasicAuth(username, password)
    else:
        auth = None

    return KodiNotificationService(hass, url, auth)


class KodiNotificationService(BaseNotificationService):
    """Implement the notification service for Kodi."""

    def __init__(self, hass, url, auth=None):
        """Initialize the service."""
        self._url = url

        kwargs = {"timeout": DEFAULT_TIMEOUT, "session": async_get_clientsession(hass)}

        if auth is not None:
            kwargs["auth"] = auth

        self._server = jsonrpc_async.Server(self._url, **kwargs)

    async def async_send_message(self, message="", **kwargs):
        """Send a message to Kodi."""
        try:
            data = kwargs.get(ATTR_DATA) or {}

            displaytime = int(data.get(ATTR_DISPLAYTIME, 10000))
            icon = data.get(ATTR_ICON, "info")
            title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
            await self._server.GUI.ShowNotification(title, message, icon, displaytime)

        except jsonrpc_async.TransportError:
            _LOGGER.warning("Unable to fetch Kodi data. Is Kodi online?")
