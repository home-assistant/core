"""Support for ESPHome cameras."""
from __future__ import annotations

import asyncio

from aioesphomeapi import CameraInfo, CameraState

from homeassistant.components import camera
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import EsphomeBaseEntity, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
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


class EsphomeCamera(Camera, EsphomeBaseEntity):
    """A camera implementation for ESPHome."""

    def __init__(self, entry_id: str, component_key: str, key: int):
        """Initialize."""
        Camera.__init__(self)
        EsphomeBaseEntity.__init__(self, entry_id, component_key, key)
        self._image_cond = asyncio.Condition()

    @property
    def _static_info(self) -> CameraInfo:
        return super()._static_info

    @property
    def _state(self) -> CameraState | None:
        return super()._state

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                (
                    f"esphome_{self._entry_id}"
                    f"_update_{self._component_key}_{self._key}"
                ),
                self._on_state_update,
            )
        )

    async def _on_state_update(self) -> None:
        """Notify listeners of new image when update arrives."""
        self.async_write_ha_state()
        async with self._image_cond:
            self._image_cond.notify_all()

    async def async_camera_image(self) -> bytes | None:
        """Return single camera image bytes."""
        if not self.available:
            return None
        await self._client.request_single_image()
        async with self._image_cond:
            await self._image_cond.wait()
            if not self.available:
                return None
            return self._state.image[:]

    async def _async_camera_stream_image(self) -> bytes | None:
        """Return a single camera image in a stream."""
        if not self.available:
            return None
        await self._client.request_image_stream()
        async with self._image_cond:
            await self._image_cond.wait()
            if not self.available:
                return None
            return self._state.image[:]

    async def handle_async_mjpeg_stream(self, request):
        """Serve an HTTP MJPEG stream from the camera."""
        return await camera.async_get_still_stream(
            request, self._async_camera_stream_image, camera.DEFAULT_CONTENT_TYPE, 0.0
        )
