"""Support for Ubiquiti's UniFi Protect NVR."""
from __future__ import annotations

from collections.abc import Generator
import logging
from typing import cast

from pyunifiprotect.data import (
    Camera as UFPCamera,
    CameraChannel,
    ModelType,
    ProtectAdoptableDeviceModel,
    ProtectModelWithId,
    StateType,
)

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BITRATE,
    ATTR_CHANNEL_ID,
    ATTR_FPS,
    ATTR_HEIGHT,
    ATTR_WIDTH,
    DISPATCH_ADOPT,
    DISPATCH_CHANNELS,
    DOMAIN,
)
from .data import ProtectData
from .entity import ProtectDeviceEntity
from .utils import async_dispatch_id as _ufpd

_LOGGER = logging.getLogger(__name__)


def get_camera_channels(
    data: ProtectData,
    ufp_device: UFPCamera | None = None,
) -> Generator[tuple[UFPCamera, CameraChannel, bool], None, None]:
    """Get all the camera channels."""

    devices = (
        data.get_by_types({ModelType.CAMERA}) if ufp_device is None else [ufp_device]
    )
    for camera in devices:
        camera = cast(UFPCamera, camera)
        if not camera.channels:
            if ufp_device is None:
                # only warn on startup
                _LOGGER.warning(
                    "Camera does not have any channels: %s (id: %s)",
                    camera.display_name,
                    camera.id,
                )
            data.async_add_pending_camera_id(camera.id)
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


def _async_camera_entities(
    data: ProtectData, ufp_device: UFPCamera | None = None
) -> list[ProtectDeviceEntity]:
    disable_stream = data.disable_stream
    entities: list[ProtectDeviceEntity] = []
    for camera, channel, is_default in get_camera_channels(data, ufp_device):
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
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover cameras on a UniFi Protect NVR."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]

    async def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        if not isinstance(device, UFPCamera):
            return

        entities = _async_camera_entities(data, ufp_device=device)
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(hass, _ufpd(entry, DISPATCH_ADOPT), _add_new_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, _ufpd(entry, DISPATCH_CHANNELS), _add_new_device)
    )

    entities = _async_camera_entities(data)
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
            self._attr_unique_id = f"{self.device.mac}_{self.channel.id}"
            self._attr_name = f"{self.device.display_name} {self.channel.name}"
        else:
            self._attr_unique_id = f"{self.device.mac}_{self.channel.id}_insecure"
            self._attr_name = f"{self.device.display_name} {self.channel.name} Insecure"
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
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        self.channel = self.device.channels[self.channel.id]
        motion_enabled = self.device.recording_settings.enable_motion_detection
        self._attr_motion_detection_enabled = (
            motion_enabled if motion_enabled is not None else True
        )
        self._attr_is_recording = (
            self.device.state == StateType.CONNECTED and self.device.is_recording
        )
        is_connected = (
            self.data.last_update_success and self.device.state == StateType.CONNECTED
        )
        # some cameras have detachable lens that could cause the camera to be offline
        self._attr_available = is_connected and self.device.is_video_ready

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

    async def async_enable_motion_detection(self) -> None:
        """Call the job and enable motion detection."""
        await self.device.set_motion_detection(True)

    async def async_disable_motion_detection(self) -> None:
        """Call the job and disable motion detection."""
        await self.device.set_motion_detection(False)
