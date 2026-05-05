"""Generic HTTP media proxy for media player and media source thumbnails.

Rewrites http:// thumbnail URLs to route through HA over HTTPS, preventing
mixed-content blocking when the frontend is served via HTTPS.

Uses HA's built-in async_sign_path for URL authorization — the same JWT-based
mechanism used by async_process_play_media_url for cast devices.
"""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Final

import aiohttp
from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL, CONTENT_TYPE

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

_FETCH_TIMEOUT: Final = aiohttp.ClientTimeout(
    total=None, connect=10, sock_connect=10, sock_read=30
)

_CHUNK_SIZE: Final[int] = 64 * 1024  # 64 KB chunks


class MediaProxyView(HomeAssistantView):
    """Proxy an http:// URL through HA over HTTPS.

    The request must carry a valid authSig query parameter (produced by
    async_sign_path / async_get_media_proxy_url). The existing HA auth
    middleware validates the JWT and sets KEY_AUTHENTICATED — no custom
    token scheme needed.

    Responses are streamed chunk-by-chunk rather than buffered, so memory
    usage is bounded to a single chunk regardless of image size.
    """

    requires_auth = False
    url = "/api/media_proxy"
    name = "api:media_proxy"

    async def get(self, request: web.Request) -> web.StreamResponse | web.Response:
        """Fetch and stream a proxied media resource."""
        if not request[KEY_AUTHENTICATED]:
            return web.Response(status=HTTPStatus.UNAUTHORIZED)

        hass: HomeAssistant = request.app["hass"]
        target_url = request.query.get("url", "")

        if not target_url or not target_url.startswith("http://"):
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        websession = async_get_clientsession(hass)
        try:
            async with websession.get(target_url, timeout=_FETCH_TIMEOUT) as upstream:
                if upstream.status != HTTPStatus.OK:
                    return web.Response(status=HTTPStatus.BAD_GATEWAY)

                content_type = (
                    upstream.headers.get(CONTENT_TYPE, "application/octet-stream")
                    .split(";")[0]
                    .strip()
                )

                response = web.StreamResponse(
                    headers={
                        CONTENT_TYPE: content_type,
                        CACHE_CONTROL: "max-age=3600",
                    }
                )
                await response.prepare(request)

                async for chunk in upstream.content.iter_chunked(_CHUNK_SIZE):
                    await response.write(chunk)

                await response.write_eof()
                return response

        except aiohttp.ClientError as err:
            _LOGGER.debug("Error proxying media from %s: %s", target_url, err)
            return web.Response(status=HTTPStatus.BAD_GATEWAY)
