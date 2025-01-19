"""Support for TPLink camera entities."""

import asyncio
from dataclasses import dataclass
import logging
import time

from aiohttp import web
from haffmpeg.camera import CameraMjpeg
from kasa import Credentials, Device, Module, StreamResolution
from kasa.smartcam.modules import Camera as CameraModule

from homeassistant.components import ffmpeg, stream
from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigFlowContext
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry, legacy_device_id
from .const import CONF_CAMERA_CREDENTIALS
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, TPLinkModuleEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TPLinkCameraEntityDescription(
    CameraEntityDescription, TPLinkModuleEntityDescription
):
    """Base class for camera entity description."""


# Coordinator is used to centralize the data updates
# For actions the integration handles locking of concurrent device request
PARALLEL_UPDATES = 0

CAMERA_DESCRIPTIONS: tuple[TPLinkCameraEntityDescription, ...] = (
    TPLinkCameraEntityDescription(
        key="live_view",
        translation_key="live_view",
        available_fn=lambda dev: dev.is_on,
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
    camera_credentials = data.camera_credentials
    live_view = data.live_view
    ffmpeg_manager = ffmpeg.get_ffmpeg_manager(hass)

    async_add_entities(
        TPLinkCameraEntity(
            device,
            parent_coordinator,
            description,
            camera_module=camera_module,
            parent=None,
            ffmpeg_manager=ffmpeg_manager,
            camera_credentials=camera_credentials,
        )
        for description in CAMERA_DESCRIPTIONS
        if (camera_module := device.modules.get(Module.Camera)) and live_view
    )


class TPLinkCameraEntity(CoordinatedTPLinkEntity, Camera):
    """Representation of a TPLink camera."""

    IMAGE_INTERVAL = 5 * 60

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
        camera_credentials: Credentials | None,
    ) -> None:
        """Initialize a TPlink camera."""
        self.entity_description = description
        self._camera_module = camera_module
        self._video_url = camera_module.stream_rtsp_url(
            camera_credentials, stream_resolution=StreamResolution.SD
        )
        self._image: bytes | None = None
        super().__init__(device, coordinator, parent=parent)
        Camera.__init__(self)
        self._ffmpeg_manager = ffmpeg_manager
        self._image_lock = asyncio.Lock()
        self._last_update: float = 0
        self._camera_credentials = camera_credentials
        self._can_stream = True
        self._http_mpeg_stream_running = False

    def _get_unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{legacy_device_id(self._device)}-{self.entity_description.key}"

    @callback
    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        self._attr_is_on = self._camera_module.is_on
        return self.entity_description.available_fn(self._device)

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return self._camera_module.stream_rtsp_url(
            self._camera_credentials, stream_resolution=StreamResolution.HD
        )

    async def _async_check_stream_auth(self, video_url: str) -> None:
        """Check for an auth error and start reauth flow."""
        try:
            await stream.async_check_stream_client_error(self.hass, video_url)
        except stream.StreamOpenClientError as ex:
            if ex.error_code is stream.StreamClientError.Unauthorized:
                _LOGGER.debug(
                    "Camera stream failed authentication for %s",
                    self._device.host,
                )
                self._can_stream = False
                self.coordinator.config_entry.async_start_reauth(
                    self.hass,
                    ConfigFlowContext(
                        reauth_source=CONF_CAMERA_CREDENTIALS,  # type: ignore[typeddict-unknown-key]
                    ),
                    {"device": self._device},
                )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        now = time.monotonic()

        if self._image and now - self._last_update < self.IMAGE_INTERVAL:
            return self._image

        # Don't try to capture a new image if a stream is running
        if self._http_mpeg_stream_running:
            return self._image

        if self._can_stream and (video_url := self._video_url):
            # Sometimes the front end makes multiple image requests
            async with self._image_lock:
                if self._image and (now - self._last_update) < self.IMAGE_INTERVAL:
                    return self._image

                _LOGGER.debug("Updating camera image for %s", self._device.host)
                image = await ffmpeg.async_get_image(
                    self.hass,
                    video_url,
                    width=width,
                    height=height,
                )
                if image:
                    self._image = image
                    self._last_update = now
                    _LOGGER.debug("Updated camera image for %s", self._device.host)
                # This coroutine is called by camera with an asyncio.timeout
                # so image could be None whereas an auth issue returns b''
                elif image == b"":
                    _LOGGER.debug(
                        "Empty camera image returned for %s", self._device.host
                    )
                    # image could be empty if a stream is running so check for explicit auth error
                    await self._async_check_stream_auth(video_url)
                else:
                    _LOGGER.debug(
                        "None camera image returned for %s", self._device.host
                    )

        return self._image

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera.

        The frontend falls back to calling this method if the HLS
        stream fails.
        """
        _LOGGER.debug("Starting http mjpeg stream for %s", self._device.host)
        if self._video_url is None or self._can_stream is False:
            return None

        mjpeg_stream = CameraMjpeg(self._ffmpeg_manager.binary)
        await mjpeg_stream.open_camera(self._video_url)
        self._http_mpeg_stream_running = True
        try:
            stream_reader = await mjpeg_stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg_manager.ffmpeg_stream_content_type,
            )
        finally:
            self._http_mpeg_stream_running = False
            await mjpeg_stream.close()
            _LOGGER.debug("Stopped http mjpeg stream for %s", self._device.host)

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        await self._camera_module.set_state(True)

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        await self._camera_module.set_state(False)
