"""Component providing support for Reolink IP cameras."""
from __future__ import annotations

import datetime as dt
import logging

from aiohttp import web
from aiohttp.typedefs import LooseHeaders
from reolink_aio.api import DUAL_LENS_MODELS
from reolink_aio.exceptions import InvalidContentTypeError
from reolink_aio.typings import VOD_download

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData, view as view_module
from .const import DOMAIN
from .entity import ReolinkChannelCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]
    host = reolink_data.host

    if not hass.data[DOMAIN].get("views_configured", False) and hass.data[
        DOMAIN
    ].setdefault("views_configured", True):
        view_module.async_setup_views(hass)

    cameras = []
    for channel in host.api.stream_channels:
        streams = ["sub", "main", "snapshots_sub", "snapshots_main"]
        if host.api.protocol in ["rtmp", "flv"]:
            streams.append("ext")

        if host.api.supported(channel, "autotrack_stream"):
            streams.extend(
                ["autotrack_sub", "autotrack_snapshots_sub", "autotrack_snapshots_main"]
            )

        for stream in streams:
            stream_url = await host.api.get_stream_source(channel, stream)
            if stream_url is None and "snapshots" not in stream:
                continue
            cameras.append(ReolinkCamera(reolink_data, channel, stream))

    async_add_entities(cameras)


class ReolinkDownloadResponse(web.StreamResponse):
    """Stream repeater similar to web.FileResponse."""

    def __init__(
        self,
        vod: VOD_download,
        status: int = 200,
        reason: str | None = None,
        headers: LooseHeaders | None = None,
    ) -> None:
        """Init Response."""
        super().__init__(status=status, reason=reason, headers=headers)
        self._vod = vod

    async def _send_vod(self, request: web.BaseRequest):
        writer = await super().prepare(request)
        assert writer is not None

        transport = request.transport
        assert transport is not None

        vod = self._vod
        async for chunk in vod.stream.iter_any():
            if transport.is_closing():
                _LOGGER.debug("Client closed stream, aborting download")
                break
            await writer.write(chunk)

        _LOGGER.debug("Closing VOD")
        vod.close()
        await writer.drain()
        return writer

    async def prepare(self, request: web.BaseRequest):
        """Prepare response."""

        _LOGGER.debug("Preparing VOD for download (%s)", self._vod.filename)
        vod = self._vod
        if vod.etag:
            self.etag = vod.etag.replace('"', "")
        self.content_length = vod.length

        writer = await self._send_vod(request)
        await writer.write_eof()
        return writer


class ReolinkCamera(ReolinkChannelCoordinatorEntity, Camera):
    """An implementation of a Reolink IP camera."""

    _attr_supported_features: CameraEntityFeature = CameraEntityFeature.STREAM

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        stream: str,
    ) -> None:
        """Initialize Reolink camera stream."""
        ReolinkChannelCoordinatorEntity.__init__(self, reolink_data, channel)
        Camera.__init__(self)

        self._stream = stream

        stream_name = self._stream.replace("_", " ")
        if self._host.api.model in DUAL_LENS_MODELS:
            self._attr_name = f"{stream_name} lens {self._channel}"
        else:
            self._attr_name = stream_name
        stream_id = self._stream
        if stream_id == "snapshots_main":
            stream_id = "snapshots"
        self._attr_unique_id = f"{self._host.unique_id}_{self._channel}_{stream_id}"
        self._attr_entity_registry_enabled_default = stream in ["sub", "autotrack_sub"]

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return await self._host.api.get_stream_source(self._channel, self._stream)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        return await self._host.api.get_snapshot(self._channel, self._stream)

    async def async_get_camera_time(self):
        """Get camera time."""
        if now := self._host.api.time():
            return now
        now = await self._host.api.async_get_time()
        return now

    async def async_get_timezone(self):
        """Get camera tzinfo."""
        if tz := self._host.api.timezone():
            return tz
        tz = (await self.async_get_camera_time()).tzinfo
        return tz

    async def handle_async_download_search(
        self,
        start: dt.datetime | dt.date | None = None,
        end: dt.datetime | dt.date | None = None,
        status_only: bool = False,
    ):
        """Get Camera VODs between start and end date."""

        if start is None:
            _start = await self.async_get_camera_time()
        elif not isinstance(start, dt.datetime):
            ct = await self.async_get_camera_time()
            _start = dt.datetime.combine(
                start, ct.time() if ct.date() == start else dt.time.min, ct.tzinfo
            )
        elif start.tzinfo is None:
            _start = start.replace(tzinfo=await self.async_get_timezone())
        else:
            _start = start

        if end is None:
            _end = _start
            _start = dt.datetime.combine(_start.date(), dt.time.min, _start.tzinfo)
        elif not isinstance(end, dt.datetime):
            ct = await self.async_get_camera_time()
            _end = dt.datetime.combine(
                end, ct.time() if ct.date() == end else dt.time.max, ct.tzinfo
            )
        elif end.tzinfo is None:
            _end = end.replace(tzinfo=_start.tzinfo)
        else:
            _end = end

        if _start > _end:
            [_start, _end] = [_end, _start]

        return await self._host.api.request_vod_files(
            self._channel, _start, _end, status_only, "main"  # self._stream
        )

    async def handle_async_download_stream(self, filename: str) -> web.StreamResponse:
        """Generate a Download Response to a requested file."""

        try:
            vod = await self._host.api.download_vod(filename)
        except InvalidContentTypeError as exc:
            raise web.HTTPServerError(
                reason="Cannot download multiple files at once."
            ) from exc

        return ReolinkDownloadResponse(vod)
