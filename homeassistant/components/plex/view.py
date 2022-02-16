"""Implement a view to provide proxied Plex thumbnails to the media browser."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from http import HTTPStatus
import logging

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL, CONTENT_TYPE
from aiohttp.typedefs import LooseHeaders
import async_timeout
from yarl import URL

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN as PLEX_DOMAIN, SERVERS

_LOGGER = logging.getLogger(__name__)


class PlexImageView(HomeAssistantView):
    """Media player view to serve a Plex image."""

    requires_auth = False
    name = "api:plex:image"

    def __init__(self, hass: HomeAssistant, server_id: str) -> None:
        """Initialize a media player view."""
        self.hass = hass
        self.server_id = server_id
        self.url = f"/api/plex_image_proxy/{server_id}"
        self.extra_urls = [
            self.url + "/{media_content_id}",
        ]

    async def get(
        self,
        request: web.Request,
        media_content_id: str | None = None,
    ) -> web.Response:
        """Start a get request."""
        if not request[KEY_AUTHENTICATED]:
            return web.Response(status=HTTPStatus.UNAUTHORIZED)

        server = self.hass.data[PLEX_DOMAIN][SERVERS][self.server_id]
        if media_content_id:
            image_url = server.thumbnail_cache.get(media_content_id)
            data, content_type = await self._async_fetch_image(image_url)

        if data is None:
            return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

        headers: LooseHeaders = {CACHE_CONTROL: "max-age=3600"}
        return web.Response(body=data, content_type=content_type, headers=headers)

    async def _async_fetch_image(self, url: str) -> tuple[bytes | None, str | None]:
        """Retrieve an image."""
        content, content_type = (None, None)
        websession = async_get_clientsession(self.hass)
        with suppress(asyncio.TimeoutError), async_timeout.timeout(10):
            response = await websession.get(url)
            if response.status == HTTPStatus.OK:
                content = await response.read()
                if content_type := response.headers.get(CONTENT_TYPE):
                    content_type = content_type.split(";")[0]

        if content is None:
            url_parts = URL(url)
            if url_parts.user is not None:
                url_parts = url_parts.with_user("xxxx")
            if url_parts.password is not None:
                url_parts = url_parts.with_password("xxxxxxxx")
            url = str(url_parts)
            _LOGGER.warning("Error retrieving proxied image from %s", url)

        return content, content_type
