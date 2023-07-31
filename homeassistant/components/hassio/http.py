"""HTTP Support for Hass.io."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
import os
import re
from urllib.parse import quote, unquote

import aiohttp
from aiohttp import web
from aiohttp.client import ClientTimeout
from aiohttp.hdrs import (
    AUTHORIZATION,
    CACHE_CONTROL,
    CONTENT_ENCODING,
    CONTENT_LENGTH,
    CONTENT_TYPE,
    TRANSFER_ENCODING,
)
from aiohttp.web_exceptions import HTTPBadGateway

from homeassistant.components.http import (
    KEY_AUTHENTICATED,
    KEY_HASS_USER,
    HomeAssistantView,
)
from homeassistant.components.onboarding import async_is_onboarded
from homeassistant.core import HomeAssistant

from .const import X_HASS_SOURCE

_LOGGER = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 1024 * 1024 * 1024

NO_TIMEOUT = re.compile(
    r"^(?:"
    r"|backups/.+/full"
    r"|backups/.+/partial"
    r"|backups/[^/]+/(?:upload|download)"
    r")$"
)

# fmt: off
# Onboarding can upload backups and restore it
PATHS_NOT_ONBOARDED = re.compile(
    r"^(?:"
    r"|backups/[a-f0-9]{8}(/info|/new/upload|/download|/restore/full|/restore/partial)?"
    r"|backups/new/upload"
    r")$"
)

# Authenticated users manage backups + download logs, changelog and documentation
PATHS_ADMIN = re.compile(
    r"^(?:"
    r"|backups/[a-f0-9]{8}(/info|/download|/restore/full|/restore/partial)?"
    r"|backups/new/upload"
    r"|audio/logs"
    r"|cli/logs"
    r"|core/logs"
    r"|dns/logs"
    r"|host/logs"
    r"|multicast/logs"
    r"|observer/logs"
    r"|supervisor/logs"
    r"|addons/[^/]+/(changelog|documentation|logs)"
    r")$"
)

# Unauthenticated requests come in for Supervisor panel + add-on images
PATHS_NO_AUTH = re.compile(
    r"^(?:"
    r"|app/.*"
    r"|(store/)?addons/[^/]+/(logo|icon)"
    r")$"
)

NO_STORE = re.compile(
    r"^(?:"
    r"|app/entrypoint.js"
    r")$"
)
# pylint: enable=implicit-str-concat
# fmt: on

RESPONSE_HEADERS_FILTER = {
    TRANSFER_ENCODING,
    CONTENT_LENGTH,
    CONTENT_TYPE,
    CONTENT_ENCODING,
}


class HassIOView(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio"
    url = "/api/hassio/{path:.+}"
    requires_auth = False

    def __init__(self, host: str, websession: aiohttp.ClientSession) -> None:
        """Initialize a Hass.io base view."""
        self._host = host
        self._websession = websession

    async def _handle(self, request: web.Request, path: str) -> web.StreamResponse:
        """Return a client request with proxy origin for Hass.io supervisor.

        Use cases:
        - Onboarding allows restoring backups
        - Load Supervisor panel and add-on logo unauthenticated
        - User upload/restore backups
        """
        # No bullshit
        if path != unquote(path):
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        hass: HomeAssistant = request.app["hass"]
        is_admin = request[KEY_AUTHENTICATED] and request[KEY_HASS_USER].is_admin
        authorized = is_admin

        if is_admin:
            allowed_paths = PATHS_ADMIN

        elif not async_is_onboarded(hass):
            allowed_paths = PATHS_NOT_ONBOARDED

            # During onboarding we need the user to manage backups
            authorized = True

        else:
            # Either unauthenticated or not an admin
            allowed_paths = PATHS_NO_AUTH

        no_auth_path = PATHS_NO_AUTH.match(path)
        headers = {
            X_HASS_SOURCE: "core.http",
        }

        if no_auth_path:
            if request.method != "GET":
                return web.Response(status=HTTPStatus.METHOD_NOT_ALLOWED)

        else:
            if not allowed_paths.match(path):
                return web.Response(status=HTTPStatus.UNAUTHORIZED)

            if authorized:
                headers[
                    AUTHORIZATION
                ] = f"Bearer {os.environ.get('SUPERVISOR_TOKEN', '')}"

            if request.method == "POST":
                headers[CONTENT_TYPE] = request.content_type
                # _stored_content_type is only computed once `content_type` is accessed
                if path == "backups/new/upload":
                    # We need to reuse the full content type that includes the boundary
                    headers[
                        CONTENT_TYPE
                    ] = request._stored_content_type  # pylint: disable=protected-access

        try:
            client = await self._websession.request(
                method=request.method,
                url=f"http://{self._host}/{quote(path)}",
                params=request.query,
                data=request.content,
                headers=headers,
                timeout=_get_timeout(path),
            )

            # Stream response
            response = web.StreamResponse(
                status=client.status, headers=_response_header(client, path)
            )
            response.content_type = client.content_type

            if should_compress(response.content_type):
                response.enable_compression()
            await response.prepare(request)
            async for data in client.content.iter_chunked(8192):
                await response.write(data)

            return response

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on api %s request %s", path, err)

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on API request %s", path)

        raise HTTPBadGateway()

    get = _handle
    post = _handle


def _response_header(response: aiohttp.ClientResponse, path: str) -> dict[str, str]:
    """Create response header."""
    headers = {
        name: value
        for name, value in response.headers.items()
        if name not in RESPONSE_HEADERS_FILTER
    }
    if NO_STORE.match(path):
        headers[CACHE_CONTROL] = "no-store, max-age=0"
    return headers


def _get_timeout(path: str) -> ClientTimeout:
    """Return timeout for a URL path."""
    if NO_TIMEOUT.match(path):
        return ClientTimeout(connect=10, total=None)
    return ClientTimeout(connect=10, total=300)


def should_compress(content_type: str) -> bool:
    """Return if we should compress a response."""
    if content_type.startswith("image/"):
        return "svg" in content_type
    return not content_type.startswith(("video/", "audio/", "font/"))
