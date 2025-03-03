"""Support for TPLink camera entities."""

import asyncio
from dataclasses import dataclass
import logging
import time

from aiohttp import web
from haffmpeg.camera import CameraMjpeg
from kasa import Device, Module, StreamResolution

from homeassistant.components import ffmpeg, stream
from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigFlowContext
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TPLinkConfigEntry
from .const import CONF_CAMERA_CREDENTIALS
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkModuleEntity, TPLinkModuleEntityDescription

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
# For actions the integration handles locking of concurrent device request
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TPLinkCameraEntityDescription(
    CameraEntityDescription, TPLinkModuleEntityDescription
):
    """Base class for camera entity description."""


CAMERA_DESCRIPTIONS: tuple[TPLinkCameraEntityDescription, ...] = (
    TPLinkCameraEntityDescription(
        key="live_view",
        translation_key="live_view",
        available_fn=lambda dev: dev.is_on,
        exists_fn=lambda dev, entry: (
            (rtd := entry.runtime_data) is not None
            and rtd.live_view is True
            and (cam_creds := rtd.camera_credentials) is not None
            and (cm := dev.modules.get(Module.Camera)) is not None
            and cm.stream_rtsp_url(cam_creds) is not None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up camera entities."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    known_child_device_ids: set[str] = set()
    first_check = True

    def _check_device() -> None:
        entities = CoordinatedTPLinkModuleEntity.entities_for_device_and_its_children(
            hass=hass,
            device=device,
            coordinator=parent_coordinator,
            entity_class=TPLinkCameraEntity,
            descriptions=CAMERA_DESCRIPTIONS,
            platform_domain=CAMERA_DOMAIN,
            known_child_device_ids=known_child_device_ids,
            first_check=first_check,
        )
        async_add_entities(entities)

    _check_device()
    first_check = False
    config_entry.async_on_unload(parent_coordinator.async_add_listener(_check_device))


class TPLinkCameraEntity(CoordinatedTPLinkModuleEntity, Camera):
    """Representation of a TPLink camera."""

    IMAGE_INTERVAL = 5 * 60

    _attr_supported_features = CameraEntityFeature.STREAM | CameraEntityFeature.ON_OFF

    entity_description: TPLinkCameraEntityDescription

    _ffmpeg_manager: ffmpeg.FFmpegManager

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        description: TPLinkCameraEntityDescription,
        *,
        parent: Device | None = None,
    ) -> None:
        """Initialize a TPlink camera."""
        super().__init__(device, coordinator, description=description, parent=parent)
        Camera.__init__(self)

        self._camera_module = device.modules[Module.Camera]
        self._camera_credentials = (
            coordinator.config_entry.runtime_data.camera_credentials
        )
        self._video_url = self._camera_module.stream_rtsp_url(
            self._camera_credentials, stream_resolution=StreamResolution.SD
        )
        self._image: bytes | None = None
        self._image_lock = asyncio.Lock()
        self._last_update: float = 0
        self._can_stream = True
        self._http_mpeg_stream_running = False

    async def async_added_to_hass(self) -> None:
        """Call update attributes after the device is added to the platform."""
        await super().async_added_to_hass()

        self._ffmpeg_manager = ffmpeg.get_ffmpeg_manager(self.hass)

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
