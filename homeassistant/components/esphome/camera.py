"""Support for ESPHome cameras."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
from typing import Any

from aioesphomeapi import CameraInfo, CameraState
from aiohttp import web

from homeassistant.components import camera
from homeassistant.components.camera import Camera
from homeassistant.core import callback

from .entity import EsphomeEntity, platform_async_setup_entry

PARALLEL_UPDATES = 0


class EsphomeCamera(Camera, EsphomeEntity[CameraInfo, CameraState]):
    """A camera implementation for ESPHome."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize."""
        Camera.__init__(self)
        EsphomeEntity.__init__(self, *args, **kwargs)
        self._loop = asyncio.get_running_loop()
        self._image_futures: list[asyncio.Future[bool | None]] = []

    @callback
    def _set_futures(self, result: bool) -> None:
        """Set futures to done."""
        for future in self._image_futures:
            if not future.done():
                future.set_result(result)
        self._image_futures.clear()

    @callback
    def _on_device_update(self) -> None:
        """Handle device going available or unavailable."""
        super()._on_device_update()
        if not self.available:
            self._set_futures(False)

    @callback
    def _on_state_update(self) -> None:
        """Notify listeners of new image when update arrives."""
        super()._on_state_update()
        self._set_futures(True)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return single camera image bytes."""
        return await self._async_request_image(self._client.request_single_image)

    async def _async_request_image(
        self, request_method: Callable[[], None]
    ) -> bytes | None:
        """Wait for an image to be available and return it."""
        if not self.available:
            return None
        image_future = self._loop.create_future()
        self._image_futures.append(image_future)
        request_method()
        if not await image_future:
            return None
        return self._state.data

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse:
        """Serve an HTTP MJPEG stream from the camera."""
        stream_request = partial(
            self._async_request_image, self._client.request_image_stream
        )
        return await camera.async_get_still_stream(
            request, stream_request, camera.DEFAULT_CONTENT_TYPE, 0.0
        )


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=CameraInfo,
    entity_type=EsphomeCamera,
    state_type=CameraState,
)
