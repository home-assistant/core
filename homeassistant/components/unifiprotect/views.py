"""UniFi Protect Integration views."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from aiohttp import web
from uiprotect.data import Camera, Event
from uiprotect.exceptions import ClientError

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .data import ProtectData, async_get_data_for_entry_id, async_get_data_for_nvr_id

_LOGGER = logging.getLogger(__name__)


@callback
def async_generate_thumbnail_url(
    event_id: str,
    nvr_id: str,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Generate URL for event thumbnail."""

    url_format = ThumbnailProxyView.url
    if TYPE_CHECKING:
        assert url_format is not None
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

    url_format = VideoProxyView.url
    if TYPE_CHECKING:
        assert url_format is not None
    return url_format.format(
        nvr_id=event.api.bootstrap.nvr.id,
        camera_id=event.camera_id,
        start=event.start.replace(microsecond=0).isoformat(),
        end=event.end.replace(microsecond=0).isoformat(),
    )


@callback
def async_generate_proxy_event_video_url(
    nvr_id: str,
    event_id: str,
) -> str:
    """Generate proxy URL for event video."""

    url_format = VideoEventProxyView.url
    if TYPE_CHECKING:
        assert url_format is not None
    return url_format.format(nvr_id=nvr_id, event_id=event_id)


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

    def _get_data_or_404(self, nvr_id_or_entry_id: str) -> ProtectData | web.Response:
        if data := (
            async_get_data_for_nvr_id(self.hass, nvr_id_or_entry_id)
            or async_get_data_for_entry_id(self.hass, nvr_id_or_entry_id)
        ):
            return data
        return _404("Invalid NVR ID")

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


class VideoEventProxyView(ProtectProxyView):
    """View to proxy video clips for events from UniFi Protect."""

    url = "/api/unifiprotect/video/{nvr_id}/{event_id}"
    name = "api:unifiprotect_videoEventView"

    async def get(
        self, request: web.Request, nvr_id: str, event_id: str
    ) -> web.StreamResponse:
        """Get Camera Video clip for an event."""

        data = self._get_data_or_404(nvr_id)
        if isinstance(data, web.Response):
            return data

        try:
            event = await data.api.get_event(event_id)
        except ClientError:
            return _404(f"Invalid event ID: {event_id}")
        if event.start is None or event.end is None:
            return _400("Event is still ongoing")
        camera = self._async_get_camera(data, str(event.camera_id))
        if camera is None:
            return _404(f"Invalid camera ID: {event.camera_id}")
        if not camera.can_read_media(data.api.bootstrap.auth_user):
            return _403(f"User cannot read media from camera: {camera.id}")

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
            await camera.get_video(event.start, event.end, iterator_callback=iterator)
        except ClientError as err:
            return _404(err)

        if response.prepared:
            await response.write_eof()
        return response
