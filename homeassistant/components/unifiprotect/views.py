"""UniFi Protect Integration views."""
from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
import logging
from typing import Any
from urllib.parse import urlencode

from aiohttp import web
from pyunifiprotect.data import Event
from pyunifiprotect.exceptions import NvrError

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .data import ProtectData

_LOGGER = logging.getLogger(__name__)


@callback
def _client_error(message: Any, code: HTTPStatus) -> web.Response:
    _LOGGER.warning("Client error (%s): %s", code.value, message)
    if code == HTTPStatus.BAD_REQUEST:
        return web.Response(body=message, status=code)
    return web.Response(status=code)


@callback
def _400(message: Any) -> web.Response:
    return _client_error(message, HTTPStatus.BAD_REQUEST)


@callback
def _403(message: Any) -> web.Response:
    return _client_error(message, HTTPStatus.FORBIDDEN)


@callback
def _404(message: Any) -> web.Response:
    return _client_error(message, HTTPStatus.NOT_FOUND)


@callback
def _validate_event(event: Event) -> None:
    if event.camera is None:
        raise ValueError("Event does not have a camera")
    if not event.camera.can_read_media(event.api.bootstrap.auth_user):
        raise PermissionError(f"User cannot read media from camera: {event.camera.id}")


@callback
def async_generate_thumbnail_url(
    event: Event,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Generate URL for event thumbnail."""

    _validate_event(event)
    url_format = ThumbnailProxyView.url or "{event_id}"
    url = url_format.format(event_id=event.id)
    params = {"nvr_id": event.api.bootstrap.nvr.id}

    if width is not None:
        params["w"] = str(width)
    if height is not None:
        params["h"] = str(height)

    return f"{url}?{urlencode(params)}"


@callback
def async_generate_event_video_url(event: Event) -> str:
    """Generate URL for event video."""

    _validate_event(event)
    if event.start is None or event.end is None:
        raise ValueError("Event is ongoing")

    url_format = VideoProxyView.url or "{camera_id}"
    url = url_format.format(camera_id=event.camera_id)
    params = {
        "nvr_id": event.api.bootstrap.nvr.id,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
    }

    return f"{url}?{urlencode(params)}"


class ProtectProxyView(HomeAssistantView):
    """Base class to proxy request to UniFi Protect console."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a thumbnail proxy view."""
        self.hass = hass
        self.data = hass.data[DOMAIN]

    def _get_data_or_404(self, request: web.Request) -> ProtectData | web.Response:
        all_data: list[ProtectData] = []

        nvr_id: str | None = request.query.get("nvr_id")
        for data in self.data.values():
            if isinstance(data, ProtectData):
                if data.api.bootstrap.nvr.id == nvr_id:
                    return data
                all_data.append(data)

        if len(all_data) == 1:
            return all_data[0]
        return _404("Invalid NVR ID")


class ThumbnailProxyView(ProtectProxyView):
    """View to proxy event thumbnails from UniFi Protect."""

    requires_auth = False  # TODO: https://github.com/home-assistant/core/pull/73240
    url = "/api/ufp/thumbnail/{event_id}"
    name = "api:ufp_thumbnail"

    async def get(self, request: web.Request, event_id: str) -> web.Response:
        """Get Event Thumbnail."""

        data = self._get_data_or_404(request)
        if isinstance(data, web.Response):
            return data

        width: int | str | None = request.query.get("w")
        height: int | str | None = request.query.get("h")

        # TODO: https://github.com/home-assistant/core/pull/73240
        if isinstance(height, str):
            height = height.split("?")[0]

        if width is not None:
            try:
                width = int(width)
            except ValueError:
                return _400("Invalid width param")
        if height is not None:
            try:
                height = int(height)
            except ValueError:
                return _400("Invalid height param")

        try:
            thumbnail = await data.api.get_event_thumbnail(
                event_id, width=width, height=height
            )
        except NvrError as err:
            return _404(err)

        if thumbnail is None:
            return _404("Event thumbnail not found")

        return web.Response(body=thumbnail, content_type="image/jpeg")


class VideoProxyView(ProtectProxyView):
    """View to proxy video clips from UniFi Protect."""

    requires_auth = False  # TODO: https://github.com/home-assistant/core/pull/73240
    url = "/api/ufp/video/{camera_id}"
    name = "api:ufp_thumbnail"

    async def get(self, request: web.Request, camera_id: str) -> web.StreamResponse:
        """Get Camera Video clip."""

        data = self._get_data_or_404(request)
        if isinstance(data, web.Response):
            return data

        camera = data.api.bootstrap.cameras.get(camera_id)
        if camera is None:
            return _404(f"Invalid camera ID: {camera_id}")
        if not camera.can_read_media(data.api.bootstrap.auth_user):
            return _403(f"User cannot read media from camera: {camera.id}")

        start: str | None = request.query.get("start")
        end: str | None = request.query.get("end")

        if start is None:
            return _400("Missing start")
        if end is None:
            return _400("Missing end")

        try:
            start_dt = datetime.fromisoformat(start)
        except ValueError:
            return _400("Invalid start")

        try:
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            return _400("Invalid end")

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "video/mp4",
            },
        )

        async def iterator(total: int, chunk: bytes | None) -> None:
            if not response.prepared:
                response.content_length = total
                await response.prepare(request)

            if chunk is not None:
                await response.write(chunk)

        try:
            await camera.get_video(start_dt, end_dt, iterator_callback=iterator)
        except NvrError as err:
            return _404(err)

        if not response.prepared:
            return _404("Video not found")

        await response.write_eof()
        return response
