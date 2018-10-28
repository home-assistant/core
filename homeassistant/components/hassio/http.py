"""
Exposes regular REST commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hassio/
"""
import asyncio
import logging
import os
import re

import async_timeout
import aiohttp
from aiohttp import web
from aiohttp.hdrs import CONTENT_TYPE
from aiohttp.web_exceptions import HTTPBadGateway

from homeassistant.const import CONTENT_TYPE_TEXT_PLAIN
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView

from .const import X_HASSIO

_LOGGER = logging.getLogger(__name__)


NO_TIMEOUT = re.compile(
    r'^(?:'
    r'|homeassistant/update'
    r'|host/update'
    r'|supervisor/update'
    r'|addons/[^/]+/(?:update|install|rebuild)'
    r'|snapshots/.+/full'
    r'|snapshots/.+/partial'
    r'|snapshots/[^/]+/(?:upload|download)'
    r')$'
)

NO_AUTH = re.compile(
    r'^(?:'
    r'|app/.*'
    r'|addons/[^/]+/logo'
    r')$'
)


class HassIOView(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio"
    url = "/api/hassio/{path:.+}"
    requires_auth = False

    def __init__(self, host, websession):
        """Initialize a Hass.io base view."""
        self._host = host
        self._websession = websession

    async def _handle(self, request, path):
        """Route data to Hass.io."""
        if _need_auth(path) and not request[KEY_AUTHENTICATED]:
            return web.Response(status=401)

        client = await self._command_proxy(path, request)

        data = await client.read()
        if path.endswith('/logs'):
            return _create_response_log(client, data)
        return _create_response(client, data)

    get = _handle
    post = _handle

    async def _command_proxy(self, path, request):
        """Return a client request with proxy origin for Hass.io supervisor.

        This method is a coroutine.
        """
        read_timeout = _get_timeout(path)
        hass = request.app['hass']

        try:
            data = None
            headers = {X_HASSIO: os.environ.get('HASSIO_TOKEN', "")}
            with async_timeout.timeout(10, loop=hass.loop):
                data = await request.read()
                if data:
                    headers[CONTENT_TYPE] = request.content_type
                else:
                    data = None

            method = getattr(self._websession, request.method.lower())
            client = await method(
                "http://{}/{}".format(self._host, path), data=data,
                headers=headers, timeout=read_timeout
            )

            return client

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on api %s request %s", path, err)

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on API request %s", path)

        raise HTTPBadGateway()


def _create_response(client, data):
    """Convert a response from client request."""
    return web.Response(
        body=data,
        status=client.status,
        content_type=client.content_type,
    )


def _create_response_log(client, data):
    """Convert a response from client request."""
    # Remove color codes
    log = re.sub(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", data.decode())

    return web.Response(
        text=log,
        status=client.status,
        content_type=CONTENT_TYPE_TEXT_PLAIN,
    )


def _get_timeout(path):
    """Return timeout for a URL path."""
    if NO_TIMEOUT.match(path):
        return 0
    return 300


def _need_auth(path):
    """Return if a path need authentication."""
    if NO_AUTH.match(path):
        return False
    return True
