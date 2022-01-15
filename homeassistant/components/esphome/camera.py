"""Support for ESPHome cameras."""
from __future__ import annotations

import asyncio
from typing import Any

from aioesphomeapi import CameraInfo, CameraState
from aiohttp import web

from homeassistant.components import camera
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EsphomeEntity, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up esphome cameras based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="camera",
        info_type=CameraInfo,
        entity_type=EsphomeCamera,
        state_type=CameraState,
    )


class EsphomeCamera(Camera, EsphomeEntity[CameraInfo, CameraState]):
    """A camera implementation for ESPHome."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize."""
        Camera.__init__(self)
        EsphomeEntity.__init__(self, *args, **kwargs)
        self._image_cond = asyncio.Condition()

    @callback
    def _on_state_update(self) -> None:
        """Notify listeners of new image when update arrives."""
        super()._on_state_update()
        self.hass.async_create_task(self._on_state_update_coro())

    async def _on_state_update_coro(self) -> None:
        async with self._image_cond:
            self._image_cond.notify_all()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return single camera image bytes."""
        if not self.available:
            return None
        await self._client.request_single_image()
        async with self._image_cond:
            await self._image_cond.wait()
            if not self.available:
                # Availability can change while waiting for 'self._image.cond'
                return None  # type: ignore[unreachable]
            return self._state.data[:]

    async def _async_camera_stream_image(self) -> bytes | None:
        """Return a single camera image in a stream."""
        if not self.available:
            return None
        await self._client.request_image_stream()
        async with self._image_cond:
            await self._image_cond.wait()
            if not self.available:
                # Availability can change while waiting for 'self._image.cond'
                return None  # type: ignore[unreachable]
            return self._state.data[:]

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse:
        """Serve an HTTP MJPEG stream from the camera."""
        return await camera.async_get_still_stream(
            request, self._async_camera_stream_image, camera.DEFAULT_CONTENT_TYPE, 0.0
        )
