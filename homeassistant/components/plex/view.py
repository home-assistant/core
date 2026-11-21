"""Implement a view to provide proxied Plex thumbnails to the media browser."""

from http import HTTPStatus
import logging

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL
from aiohttp.typedefs import LooseHeaders
from plexapi.exceptions import BadRequest, NotFound

from homeassistant.components.http import KEY_AUTHENTICATED, KEY_HASS, HomeAssistantView
from homeassistant.components.media_player import async_fetch_image

from .helpers import get_plex_servers
from .server import PlexServer

_LOGGER = logging.getLogger(__name__)


def _lookup_thumbnail_url(server: PlexServer, rating_key: int) -> str | None:
    """Look up the thumbnail of an item, for links returned before a reload."""
    try:
        item = server.fetch_item(rating_key)
    except NotFound, BadRequest:
        return None
    return getattr(item, "thumbUrl", None)


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
        if (server := get_plex_servers(hass).get(server_id)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        image_url = server.thumbnail_cache.get(media_content_id)
        if image_url is None and media_content_id.isdecimal():
            image_url = await hass.async_add_executor_job(
                _lookup_thumbnail_url, server, int(media_content_id)
            )
            if image_url is not None:
                server.thumbnail_cache[media_content_id] = image_url

        if image_url is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        data, content_type = await async_fetch_image(_LOGGER, hass, image_url)

        if data is None:
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)

        headers: LooseHeaders = {CACHE_CONTROL: "max-age=3600"}
        return web.Response(body=data, content_type=content_type, headers=headers)
