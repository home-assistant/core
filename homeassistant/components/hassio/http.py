"""HTTP Support for Hass.io."""
import asyncio
import logging
import os
import re
from typing import Dict, Union

import aiohttp
from aiohttp import web
from aiohttp.hdrs import CONTENT_TYPE
from aiohttp.web_exceptions import HTTPBadGateway
import async_timeout

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView

from .const import X_HASS_IS_ADMIN, X_HASS_USER_ID, X_HASSIO

_LOGGER = logging.getLogger(__name__)


NO_TIMEOUT = re.compile(
    r'^(?:'
    r'|homeassistant/update'
    r'|hassos/update'
    r'|hassos/update/cli'
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

STREAM_RESPONSE = re.compile(
    r'^(?:'
    r'|snapshots/[^/]+/(?:upload|download)'
    r')$'
)


class HassIOView(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio"
    url = "/api/hassio/{path:.+}"
    requires_auth = False

    def __init__(self, host: str, websession: aiohttp.ClientSession):
        """Initialize a Hass.io base view."""
        self._host = host
        self._websession = websession

    async def _handle(
            self, request: web.Request, path: str
    ) -> Union[web.Response, web.StreamResponse]:
        """Route data to Hass.io."""
        if _need_auth(path) and not request[KEY_AUTHENTICATED]:
            return web.Response(status=401)

        # Prepare the right proxy
        if _is_stream(path):
            return await self._stream_proxy(path, request)
        return await self._command_proxy(path, request)

    get = _handle
    post = _handle

    async def _command_proxy(
            self, path: str, request: web.Request
    ) -> web.Response:
        """Return a client request with proxy origin for Hass.io supervisor.

        This method is a coroutine.
        """
        read_timeout = _get_timeout(path)
        hass = request.app['hass']

        data = None
        headers = _init_header(request)

        try:
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

            data = await client.read()
            return web.Response(
                body=data,
                status=client.status,
                content_type=client.content_type
            )

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on api %s request %s", path, err)

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on API request %s", path)

        raise HTTPBadGateway()

    async def _stream_proxy(
            self, path: str, request: web.Request
    ) -> web.StreamResponse:
        """Return a client stream with proxy origin for Hass.io supervisor.

        This method is a coroutine.
        """
        read_timeout = _get_timeout(path)
        hass = request.app['hass']

        data = None
        headers = _init_header(request)

        try:
            method = getattr(self._websession, request.method.lower())
            client = await method(
                "http://{}/{}".format(self._host, path), data=data,
                headers=headers, timeout=read_timeout
            )

            response = web.StreamResponse()
            response.content_type = request.content_type
            try:
                await response.prepare(request)
                async for data in client.content:
                    await response.write(data)

            except (aiohttp.ClientError, aiohttp.ClientPayloadError):
                pass

            return response

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on api %s request %s", path, err)

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on API request %s", path)

        raise HTTPBadGateway()


def _init_header(request: web.Request) -> Dict[str, str]:
    """Create initial header."""
    headers = {
        X_HASSIO: os.environ.get('HASSIO_TOKEN', ""),
        CONTENT_TYPE: request.content_type,
    }

    # Add user data
    user = request.get('hass_user')
    if user is not None:
        headers[X_HASS_USER_ID] = request['hass_user'].id
        headers[X_HASS_IS_ADMIN] = str(int(request['hass_user'].is_admin))

    return headers


def _get_timeout(path: str) -> int:
    """Return timeout for a URL path."""
    if NO_TIMEOUT.match(path):
        return 0
    return 300


def _need_auth(path: str) -> bool:
    """Return if a path need authentication."""
    if NO_AUTH.match(path):
        return False
    return True


def _is_stream(path: str) -> bool:
    """Return if a path need stream response."""
    if STREAM_RESPONSE.match(path):
        return True
    return False
