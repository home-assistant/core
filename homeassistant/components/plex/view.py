"""Implement a view to provide proxied Plex thumbnails to the media browser."""
from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL
from aiohttp.typedefs import LooseHeaders

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.components.media_player import async_fetch_image
from homeassistant.core import HomeAssistant

from .const import DOMAIN as PLEX_DOMAIN, SERVERS

_LOGGER = logging.getLogger(__name__)


class PlexImageView(HomeAssistantView):
    """Media player view to serve a Plex image."""

    requires_auth = False
    name = "api:plex:image"
    url = "/api/plex_image_proxy/{server_id}/{media_content_id}"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a media player view."""
        self.hass = hass

    async def get(
        self,
        request: web.Request,
        server_id: str | None = None,
        media_content_id: str | None = None,
    ) -> web.Response:
        """Start a get request."""
        if not request[KEY_AUTHENTICATED]:
            return web.Response(status=HTTPStatus.UNAUTHORIZED)

        if (server := self.hass.data[PLEX_DOMAIN][SERVERS].get(server_id)) is None:
            return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

        if media_content_id:
            image_url = server.thumbnail_cache.get(media_content_id)
            data, content_type = await async_fetch_image(self.hass, image_url)

        if data is None:
            return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

        headers: LooseHeaders = {CACHE_CONTROL: "max-age=3600"}
        return web.Response(body=data, content_type=content_type, headers=headers)
