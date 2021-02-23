"""HTTP Support for Hass.io."""
import asyncio
import logging
import os
import re
from typing import Dict, Union

import aiohttp
from aiohttp import web
from aiohttp.hdrs import CONTENT_LENGTH, CONTENT_TYPE
from aiohttp.web_exceptions import HTTPBadGateway
import async_timeout

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.components.onboarding import async_is_onboarded
from homeassistant.const import HTTP_UNAUTHORIZED

from .const import X_HASS_IS_ADMIN, X_HASS_USER_ID, X_HASSIO

_LOGGER = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 1024 * 1024 * 1024

NO_TIMEOUT = re.compile(
    r"^(?:"
    r"|homeassistant/update"
    r"|hassos/update"
    r"|hassos/update/cli"
    r"|supervisor/update"
    r"|addons/[^/]+/(?:update|install|rebuild)"
    r"|snapshots/.+/full"
    r"|snapshots/.+/partial"
    r"|snapshots/[^/]+/(?:upload|download)"
    r")$"
)

NO_AUTH_ONBOARDING = re.compile(
    r"^(?:" r"|supervisor/logs" r"|snapshots/[^/]+/.+" r")$"
)

NO_AUTH = re.compile(
    r"^(?:" r"|app/.*" r"|addons/[^/]+/logo" r"|addons/[^/]+/icon" r")$"
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
        hass = request.app["hass"]
        if _need_auth(hass, path) and not request[KEY_AUTHENTICATED]:
            return web.Response(status=HTTP_UNAUTHORIZED)

        return await self._command_proxy(path, request)

    delete = _handle
    get = _handle
    post = _handle

    async def _command_proxy(
        self, path: str, request: web.Request
    ) -> Union[web.Response, web.StreamResponse]:
        """Return a client request with proxy origin for Hass.io supervisor.

        This method is a coroutine.
        """
        read_timeout = _get_timeout(path)
        client_timeout = 10
        data = None
        headers = _init_header(request)
        if path == "snapshots/new/upload":
            # We need to reuse the full content type that includes the boundary
            headers[
                "Content-Type"
            ] = request._stored_content_type  # pylint: disable=protected-access

            # Snapshots are big, so we need to adjust the allowed size
            request._client_max_size = (  # pylint: disable=protected-access
                MAX_UPLOAD_SIZE
            )
            client_timeout = 300

        try:
            with async_timeout.timeout(client_timeout):
                data = await request.read()

            method = getattr(self._websession, request.method.lower())
            client = await method(
                f"http://{self._host}/{path}",
                data=data,
                headers=headers,
                timeout=read_timeout,
            )

            # Simple request
            if int(client.headers.get(CONTENT_LENGTH, 0)) < 4194000:
                # Return Response
                body = await client.read()
                return web.Response(
                    content_type=client.content_type, status=client.status, body=body
                )

            # Stream response
            response = web.StreamResponse(status=client.status, headers=client.headers)
            response.content_type = client.content_type

            await response.prepare(request)
            async for data in client.content.iter_chunked(4096):
                await response.write(data)

            return response

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on api %s request %s", path, err)

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on API request %s", path)

        raise HTTPBadGateway()


def _init_header(request: web.Request) -> Dict[str, str]:
    """Create initial header."""
    headers = {
        X_HASSIO: os.environ.get("HASSIO_TOKEN", ""),
        CONTENT_TYPE: request.content_type,
    }

    # Add user data
    user = request.get("hass_user")
    if user is not None:
        headers[X_HASS_USER_ID] = request["hass_user"].id
        headers[X_HASS_IS_ADMIN] = str(int(request["hass_user"].is_admin))

    return headers


def _get_timeout(path: str) -> int:
    """Return timeout for a URL path."""
    if NO_TIMEOUT.match(path):
        return 0
    return 300


def _need_auth(hass, path: str) -> bool:
    """Return if a path need authentication."""
    if not async_is_onboarded(hass) and NO_AUTH_ONBOARDING.match(path):
        return False
    if NO_AUTH.match(path):
        return False
    return True
