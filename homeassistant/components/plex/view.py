"""Implement a view to provide proxied Plex thumbnails to the media browser."""

from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL
from aiohttp.typedefs import LooseHeaders

from homeassistant.components.http import KEY_AUTHENTICATED, KEY_HASS, HomeAssistantView
from homeassistant.components.media_player import async_fetch_image

from .const import SERVERS
from .helpers import get_plex_data

_LOGGER = logging.getLogger(__name__)


class PlexImageView(HomeAssistantView):
    """Media player view to serve a Plex image."""

    name = "api:plex:image"
    url = "/api/plex_image_proxy/{server_id}/{media_content_id}"

    async def get(
        self,
        request: web.Request,
        server_id: str,
        media_content_id: str,
    ) -> web.Response:
        """Start a get request."""
        if not request[KEY_AUTHENTICATED]:
            return web.Response(status=HTTPStatus.UNAUTHORIZED)

        hass = request.app[KEY_HASS]
        if (server := get_plex_data(hass)[SERVERS].get(server_id)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        if (image_url := server.thumbnail_cache.get(media_content_id)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        data, content_type = await async_fetch_image(_LOGGER, hass, image_url)

        if data is None:
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)

        headers: LooseHeaders = {CACHE_CONTROL: "max-age=3600"}
        return web.Response(body=data, content_type=content_type, headers=headers)
