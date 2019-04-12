"""Support for ESPHome cameras."""
import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from homeassistant.components import camera
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from . import EsphomeEntity, platform_async_setup_entry

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from aioesphomeapi import CameraInfo, CameraState  # noqa

DEPENDENCIES = ['esphome']
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType,
                            entry: ConfigEntry, async_add_entities) -> None:
    """Set up esphome cameras based on a config entry."""
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import CameraInfo, CameraState  # noqa

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='camera',
        info_type=CameraInfo, entity_type=EsphomeCamera,
        state_type=CameraState
    )


class EsphomeCamera(Camera, EsphomeEntity):
    """A camera implementation for ESPHome."""

    def __init__(self, entry_id: str, component_key: str, key: int):
        """Initialize."""
        Camera.__init__(self)
        EsphomeEntity.__init__(self, entry_id, component_key, key)
        self._image_cond = asyncio.Condition()

    @property
    def _static_info(self) -> 'CameraInfo':
        return super()._static_info

    @property
    def _state(self) -> Optional['CameraState']:
        return super()._state

    async def _on_update(self):
        """Notify listeners of new image when update arrives."""
        await super()._on_update()
        async with self._image_cond:
            self._image_cond.notify_all()

    async def async_camera_image(self) -> Optional[bytes]:
        """Return single camera image bytes."""
        if not self.available:
            return None
        await self._client.request_single_image()
        async with self._image_cond:
            await self._image_cond.wait()
            if not self.available:
                return None
            return self._state.image[:]

    async def _async_camera_stream_image(self) -> Optional[bytes]:
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
            request, self._async_camera_stream_image,
            camera.DEFAULT_CONTENT_TYPE, 0.0)
