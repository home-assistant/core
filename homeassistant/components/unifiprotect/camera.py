"""Support for Ubiquiti's UniFi Protect NVR."""
from __future__ import annotations

from collections.abc import Generator
import logging

from pyunifiprotect.api import ProtectApiClient
from pyunifiprotect.data import Camera as UFPCamera, CameraChannel, StateType

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BITRATE,
    ATTR_CHANNEL_ID,
    ATTR_FPS,
    ATTR_HEIGHT,
    ATTR_WIDTH,
    DOMAIN,
)
from .data import ProtectData
from .entity import ProtectDeviceEntity

_LOGGER = logging.getLogger(__name__)


def get_camera_channels(
    protect: ProtectApiClient,
) -> Generator[tuple[UFPCamera, CameraChannel, bool], None, None]:
    """Get all the camera channels."""
    for camera in protect.bootstrap.cameras.values():
        if not camera.channels:
            _LOGGER.warning(
                "Camera does not have any channels: %s (id: %s)", camera.name, camera.id
            )
            continue

        is_default = True
        for channel in camera.channels:
            if channel.is_package:
                yield camera, channel, True
            elif channel.is_rtsp_enabled:
                yield camera, channel, is_default
                is_default = False

        # no RTSP enabled use first channel with no stream
        if is_default:
            yield camera, camera.channels[0], True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover cameras on a UniFi Protect NVR."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]
    disable_stream = data.disable_stream

    entities = []
    for camera, channel, is_default in get_camera_channels(data.api):
        # do not enable streaming for package camera
        # 2 FPS causes a lot of buferring
        entities.append(
            ProtectCamera(
                data,
                camera,
                channel,
                is_default,
                True,
                disable_stream or channel.is_package,
            )
        )

        if channel.is_rtsp_enabled and not channel.is_package:
            entities.append(
                ProtectCamera(
                    data,
                    camera,
                    channel,
                    is_default,
                    False,
                    disable_stream,
                )
            )
    async_add_entities(entities)


class ProtectCamera(ProtectDeviceEntity, Camera):
    """A Ubiquiti UniFi Protect Camera."""

    device: UFPCamera

    def __init__(
        self,
        data: ProtectData,
        camera: UFPCamera,
        channel: CameraChannel,
        is_default: bool,
        secure: bool,
        disable_stream: bool,
    ) -> None:
        """Initialize an UniFi camera."""
        self.channel = channel
        self._secure = secure
        self._disable_stream = disable_stream
        self._last_image: bytes | None = None
        super().__init__(data, camera)

        if self._secure:
            self._attr_unique_id = f"{self.device.id}_{self.channel.id}"
            self._attr_name = f"{self.device.name} {self.channel.name}"
        else:
            self._attr_unique_id = f"{self.device.id}_{self.channel.id}_insecure"
            self._attr_name = f"{self.device.name} {self.channel.name} Insecure"
        # only the default (first) channel is enabled by default
        self._attr_entity_registry_enabled_default = is_default and secure

    @callback
    def _async_set_stream_source(self) -> None:
        disable_stream = self._disable_stream
        if not self.channel.is_rtsp_enabled:
            disable_stream = False

        rtsp_url = self.channel.rtsp_url
        if self._secure:
            rtsp_url = self.channel.rtsps_url

        # _async_set_stream_source called by __init__
        self._stream_source = (  # pylint: disable=attribute-defined-outside-init
            None if disable_stream else rtsp_url
        )
        self._attr_supported_features: int = (
            CameraEntityFeature.STREAM if self._stream_source else 0
        )

    @callback
    def _async_update_device_from_protect(self) -> None:
        super()._async_update_device_from_protect()
        self.channel = self.device.channels[self.channel.id]
        self._attr_motion_detection_enabled = (
            self.device.state == StateType.CONNECTED
            and self.device.feature_flags.has_motion_zones
        )
        self._attr_is_recording = (
            self.device.state == StateType.CONNECTED and self.device.is_recording
        )

        self._async_set_stream_source()
        self._attr_extra_state_attributes = {
            ATTR_WIDTH: self.channel.width,
            ATTR_HEIGHT: self.channel.height,
            ATTR_FPS: self.channel.fps,
            ATTR_BITRATE: self.channel.bitrate,
            ATTR_CHANNEL_ID: self.channel.id,
        }

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the Camera Image."""
        if self.channel.is_package:
            last_image = await self.device.get_package_snapshot(width, height)
        else:
            last_image = await self.device.get_snapshot(width, height)
        self._last_image = last_image
        return self._last_image

    async def stream_source(self) -> str | None:
        """Return the Stream Source."""
        return self._stream_source
