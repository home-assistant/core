"""UniFi Protect Integration views."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
import logging
from typing import Any
from urllib.parse import urlencode

from aiohttp import web
from pyunifiprotect.data import Camera, Event
from pyunifiprotect.exceptions import ClientError

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .data import ProtectData

_LOGGER = logging.getLogger(__name__)


@callback
def async_generate_thumbnail_url(
    event_id: str,
    nvr_id: str,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Generate URL for event thumbnail."""

    url_format = ThumbnailProxyView.url or "{nvr_id}/{event_id}"
    url = url_format.format(nvr_id=nvr_id, event_id=event_id)

    params = {}
    if width is not None:
        params["width"] = str(width)
    if height is not None:
        params["height"] = str(height)

    return f"{url}?{urlencode(params)}"


@callback
def async_generate_event_video_url(event: Event) -> str:
    """Generate URL for event video."""

    _validate_event(event)
    if event.start is None or event.end is None:
        raise ValueError("Event is ongoing")

    url_format = VideoProxyView.url or "{nvr_id}/{camera_id}/{start}/{end}"
    return url_format.format(
        nvr_id=event.api.bootstrap.nvr.id,
        camera_id=event.camera_id,
        start=event.start.replace(microsecond=0).isoformat(),
        end=event.end.replace(microsecond=0).isoformat(),
    )


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


class ProtectProxyView(HomeAssistantView):
    """Base class to proxy request to UniFi Protect console."""

    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a thumbnail proxy view."""
        self.hass = hass
        self.data = hass.data[DOMAIN]

    def _get_data_or_404(self, nvr_id: str) -> ProtectData | web.Response:
        all_data: list[ProtectData] = []

        for entry_id, data in self.data.items():
            if isinstance(data, ProtectData):
                if nvr_id == entry_id:
                    return data
                if data.api.bootstrap.nvr.id == nvr_id:
                    return data
                all_data.append(data)
        return _404("Invalid NVR ID")


class ThumbnailProxyView(ProtectProxyView):
    """View to proxy event thumbnails from UniFi Protect."""

    url = "/api/unifiprotect/thumbnail/{nvr_id}/{event_id}"
    name = "api:unifiprotect_thumbnail"

    async def get(
        self, request: web.Request, nvr_id: str, event_id: str
    ) -> web.Response:
        """Get Event Thumbnail."""

        data = self._get_data_or_404(nvr_id)
        if isinstance(data, web.Response):
            return data

        width: int | str | None = request.query.get("width")
        height: int | str | None = request.query.get("height")

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
        except ClientError as err:
            return _404(err)

        if thumbnail is None:
            return _404("Event thumbnail not found")

        return web.Response(body=thumbnail, content_type="image/jpeg")


class VideoProxyView(ProtectProxyView):
    """View to proxy video clips from UniFi Protect."""

    url = "/api/unifiprotect/video/{nvr_id}/{camera_id}/{start}/{end}"
    name = "api:unifiprotect_thumbnail"

    @callback
    def _async_get_camera(self, data: ProtectData, camera_id: str) -> Camera | None:
        if (camera := data.api.bootstrap.cameras.get(camera_id)) is not None:
            return camera

        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        if (entity := entity_registry.async_get(camera_id)) is None or (
            device := device_registry.async_get(entity.device_id or "")
        ) is None:
            return None

        macs = [c[1] for c in device.connections if c[0] == dr.CONNECTION_NETWORK_MAC]
        for mac in macs:
            if (ufp_device := data.api.bootstrap.get_device_from_mac(mac)) is not None:
                if isinstance(ufp_device, Camera):
                    camera = ufp_device
                    break
        return camera

    async def get(
        self, request: web.Request, nvr_id: str, camera_id: str, start: str, end: str
    ) -> web.StreamResponse:
        """Get Camera Video clip."""

        data = self._get_data_or_404(nvr_id)
        if isinstance(data, web.Response):
            return data

        camera = self._async_get_camera(data, camera_id)
        if camera is None:
            return _404(f"Invalid camera ID: {camera_id}")
        if not camera.can_read_media(data.api.bootstrap.auth_user):
            return _403(f"User cannot read media from camera: {camera.id}")

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
        except ClientError as err:
            return _404(err)

        if response.prepared:
            await response.write_eof()
        return response
