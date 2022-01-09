"""UniFi Protect Integration views."""
from __future__ import annotations

from collections.abc import Iterable
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import web
from pyunifiprotect.api import ProtectApiClient
from pyunifiprotect.exceptions import NvrError

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .data import ProtectData

_LOGGER = logging.getLogger(__name__)


def _404(message: Any) -> web.Response:
    _LOGGER.warning("Error on load thumbnail: %s", message)
    return web.Response(status=HTTPStatus.NOT_FOUND)


class ThumbnailProxyView(HomeAssistantView):
    """View to proxy event thumbnails from UniFi Protect."""

    requires_auth = False
    url = "/api/ufp/thumbnail/{event_id}"
    name = "api:ufp_thumbnail"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a thumbnail proxy view."""
        self.hass = hass
        self.data = hass.data[DOMAIN]

    def _get_access_tokens_and_instance(
        self, entity_id: str | None, nvr_id: str | None, camera_id: str | None
    ) -> tuple[Iterable, ProtectApiClient | None]:

        access_tokens: Iterable[str] = []
        api: ProtectApiClient | None = None

        entries: list[ProtectData] = list(self.data.values())
        for entry in entries:
            if entity_id is not None and entity_id in entry.access_tokens:
                access_tokens = entry.access_tokens[entity_id]
                api = entry.api
            elif nvr_id is not None and nvr_id == entry.api.bootstrap.nvr.id:
                api = entry.api
            elif camera_id is not None and camera_id in entry.api.bootstrap.cameras:
                api = entry.api

        return access_tokens, api

    async def get(self, request: web.Request, event_id: str) -> web.Response:
        """Start a get request."""

        entity_id: str | None = request.query.get("entity_id")
        nvr_id: str | None = request.query.get("nvr_id")
        camera_id: str | None = request.query.get("camera_id")
        width: int | str | None = request.query.get("w")
        height: int | str | None = request.query.get("h")
        token: str | None = request.query.get("token")

        if width is not None:
            try:
                width = int(width)
            except ValueError:
                return _404("Invalid width param")
        if height is not None:
            try:
                height = int(height)
            except ValueError:
                return _404("Invalid height param")

        access_tokens, instance = self._get_access_tokens_and_instance(
            entity_id, nvr_id, camera_id
        )

        if instance is None:
            return _404(
                "Could not find UniFi Protect instance. The `entity_id`, `nvr_id` or `camera_id` query parameter is required"
            )

        authenticated = request[KEY_AUTHENTICATED] or token in access_tokens
        if not authenticated:
            _LOGGER.debug("Thumbnail view not authenticated")
            raise web.HTTPUnauthorized()

        try:
            thumbnail = await instance.get_event_thumbnail(
                event_id, width=width, height=height
            )
        except NvrError as err:
            return _404(err)

        if thumbnail is None:
            return _404("Event thumbnail not found")

        return web.Response(body=thumbnail, content_type="image/jpeg")
