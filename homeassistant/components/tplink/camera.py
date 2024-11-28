"""Support for TPLink camera entities."""

import asyncio
from dataclasses import dataclass
import logging

from aiohttp import web
from haffmpeg.camera import CameraMjpeg
from kasa import Device, Module
from kasa.smartcam.modules import Camera as CameraModule

from homeassistant.components import ffmpeg
from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry, legacy_device_id
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, TPLinkModuleEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TPLinkCameraEntityDescription(
    CameraEntityDescription, TPLinkModuleEntityDescription
):
    """Base class for camera entity description."""


CAMERA_DESCRIPTIONS: tuple[TPLinkCameraEntityDescription, ...] = (
    TPLinkCameraEntityDescription(
        key="live_view",
        translation_key="live_view",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera entities."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device
    ffmpeg_manager = ffmpeg.get_ffmpeg_manager(hass)

    async_add_entities(
        TPLinkCameraEntity(
            device,
            parent_coordinator,
            description,
            camera_module=camera_module,
            parent=None,
            ffmpeg_manager=ffmpeg_manager,
        )
        for description in CAMERA_DESCRIPTIONS
        if (camera_module := device.modules.get(Module.Camera))
    )


class TPLinkCameraEntity(CoordinatedTPLinkEntity, Camera):
    """Representation of a TPLink camera."""

    _attr_supported_features = CameraEntityFeature.STREAM | CameraEntityFeature.ON_OFF

    entity_description: TPLinkCameraEntityDescription

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        description: TPLinkCameraEntityDescription,
        *,
        camera_module: CameraModule,
        parent: Device | None = None,
        ffmpeg_manager: ffmpeg.FFmpegManager,
    ) -> None:
        """Initialize a TPlink camera."""
        self.entity_description = description
        self._camera_module = camera_module
        self._video_url: str | None = None
        self._image: bytes | None = None
        super().__init__(device, coordinator, parent=parent)
        Camera.__init__(self)
        self._ffmpeg_manager = ffmpeg_manager
        self._image_lock = asyncio.Lock()

    def _get_unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{legacy_device_id(self._device)}-{self.entity_description}"

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._camera_module.is_on
        self._video_url = self._camera_module.stream_rtsp_url()

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return self._video_url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if self._image is None and (video_url := self._video_url):
            # Sometimes the front end makes multiple image requests
            async with self._image_lock:
                if self._image:
                    return self._image  # type: ignore[unreachable]
                image = await ffmpeg.async_get_image(
                    self.hass,
                    video_url,
                    width=width,
                    height=height,
                )
                if image:
                    self._image = image
        return self._image

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera."""
        if self._video_url is None:
            return None

        stream = CameraMjpeg(self._ffmpeg_manager.binary)
        await stream.open_camera(self._video_url)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg_manager.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        await self._camera_module.set_state(True)

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        await self._camera_module.set_state(False)
