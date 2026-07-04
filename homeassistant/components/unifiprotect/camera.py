"""Support for Ubiquiti's UniFi Protect NVR."""

import logging
from typing import override

from uiprotect.data import (
    Camera as UFPCamera,
    CameraChannel,
    ModelType,
    ProtectAdoptableDeviceModel,
    StateType,
)

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity

from .const import (
    ATTR_BITRATE,
    ATTR_CHANNEL_ID,
    ATTR_FPS,
    ATTR_HEIGHT,
    ATTR_WIDTH,
    DOMAIN,
)
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity
from .utils import async_ufp_instance_command, get_camera_base_name

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


@callback
def _create_rtsp_repair(
    hass: HomeAssistant, entry: UFPConfigEntry, camera: UFPCamera
) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"rtsp_disabled_{camera.id}",
        is_fixable=True,
        is_persistent=False,
        learn_more_url="https://www.home-assistant.io/integrations/unifiprotect/#camera-streams",
        severity=IssueSeverity.WARNING,
        translation_key="rtsp_disabled",
        translation_placeholders={"camera": camera.display_name},
        data={"entry_id": entry.entry_id, "camera_id": camera.id},
    )


@callback
def _async_camera_entities(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    data: ProtectData,
    ufp_device: UFPCamera | None = None,
) -> list[ProtectDeviceEntity]:
    """Create camera entities with stream URLs sourced from the public API.

    One entity per *active* RTSPS quality (the first is enabled by default). The
    package channel is a snapshot-first view and is always exposed (disabled by
    default), streaming only when its quality is active. When no main quality is
    active the first non-package channel is still created so snapshots work, and
    a repair offers to activate its stream. RTSPS URLs come from the public API
    (the authoritative per-camera host, so stacked consoles resolve correctly)
    with SRTP stripped for go2rtc.
    """
    disable_stream = data.disable_stream
    entities: list[ProtectDeviceEntity] = []
    cameras = data.get_cameras() if ufp_device is None else [ufp_device]
    for camera in cameras:
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

        streams = data.get_rtsps_streams(camera.id)
        active = set(streams.get_active_stream_qualities()) if streams else set()
        issue_id = f"rtsp_disabled_{camera.id}"

        has_stream = False
        package_channel: CameraChannel | None = None
        for channel in camera.channels:
            if channel.is_package:
                package_channel = channel
                continue
            if channel.rtsps_quality in active:
                entities.append(
                    ProtectCamera(data, camera, channel, not has_stream, disable_stream)
                )
                has_stream = True

        # the package channel is a snapshot-first view (very low FPS); always
        # expose it (disabled by default), streaming only when its quality is active
        if package_channel is not None:
            entities.append(
                ProtectCamera(data, camera, package_channel, False, disable_stream)
            )

        if has_stream:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue

        # no active main stream: expose the first non-package channel for snapshots
        fallback = next((c for c in camera.channels if not c.is_package), None)
        if fallback is None:
            continue
        entities.append(ProtectCamera(data, camera, fallback, True, disable_stream))
        # no repair when the stream can't be enabled anyway: a disconnected
        # camera is streamless because it is offline, not because it needs one
        if (
            disable_stream
            or camera.is_third_party_camera
            or camera.state is not StateType.CONNECTED
        ):
            ir.async_delete_issue(hass, DOMAIN, issue_id)
        else:
            _create_rtsp_repair(hass, entry, camera)
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Discover cameras on a UniFi Protect NVR."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        # AiPort inherits from Camera but should not create camera entities
        if not isinstance(device, UFPCamera) or device.model is ModelType.AIPORT:
            return
        async_add_entities(_async_camera_entities(hass, entry, data, ufp_device=device))

    data.async_subscribe_adopt(_add_new_device)
    entry.async_on_unload(
        async_dispatcher_connect(hass, data.channels_signal, _add_new_device)
    )

    # Clean up any erroneously created RTSP issues for AI Ports
    for device in data.get_by_types({ModelType.AIPORT}):
        ir.async_delete_issue(hass, DOMAIN, f"rtsp_disabled_{device.id}")

    async_add_entities(_async_camera_entities(hass, entry, data))


_DISABLE_FEATURE = CameraEntityFeature(0)
_ENABLE_FEATURE = CameraEntityFeature.STREAM


class ProtectCamera(ProtectDeviceEntity, Camera):
    """A Ubiquiti UniFi Protect Camera."""

    device: UFPCamera
    _state_attrs = (
        "_attr_available",
        "_attr_is_recording",
        "_attr_motion_detection_enabled",
    )

    def __init__(
        self,
        data: ProtectData,
        camera: UFPCamera,
        channel: CameraChannel,
        is_default: bool,
        disable_stream: bool,
    ) -> None:
        """Initialize an UniFi camera."""
        self.channel = channel
        self._disable_stream = disable_stream
        self._last_image: bytes | None = None
        super().__init__(data, camera)
        self._attr_unique_id = f"{self.device.mac}_{channel.id}"
        self._attr_name = get_camera_base_name(channel)
        # only the default (first active) channel is enabled by default
        self._attr_entity_registry_enabled_default = is_default
        # Set the stream source before finishing the init
        # because async_added_to_hass is too late and camera
        # integration uses async_internal_added_to_hass to access
        # the stream source which is called before async_added_to_hass
        self._async_set_stream_source()

    @callback
    def _async_set_stream_source(self) -> None:
        """Set the public-API RTSPS stream URL (SRTP stripped for go2rtc)."""
        quality = self.channel.rtsps_quality
        streams = self.data.get_rtsps_streams(self.device.id)
        if self._disable_stream or quality is None or streams is None:
            source = None
            if (
                streams is None
                and not self._disable_stream
                and not self.channel.is_package
            ):
                # online camera unexpectedly absent from the public bootstrap;
                # log so this is distinguishable from an intentionally off stream
                _LOGGER.debug(
                    "No public RTSPS data for camera %s (%s); using snapshots",
                    self.device.display_name,
                    self.device.id,
                )
        else:
            source = streams.get_stream_url(quality, srtp=False)
        self._attr_supported_features = _ENABLE_FEATURE if source else _DISABLE_FEATURE
        self._stream_source = source

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        updated_device = self.device
        channel = updated_device.channels[self.channel.id]
        self.channel = channel
        motion_enabled = updated_device.recording_settings.enable_motion_detection
        self._attr_motion_detection_enabled = (
            motion_enabled if motion_enabled is not None else True
        )
        state_type_is_connected = updated_device.state is StateType.CONNECTED
        self._attr_is_recording = (
            state_type_is_connected and updated_device.is_recording
        )
        is_connected = self.data.last_update_success and state_type_is_connected
        # some cameras have detachable lens that could cause the camera to be offline
        self._attr_available = is_connected and updated_device.is_video_ready

        self._async_set_stream_source()
        self._attr_extra_state_attributes = {
            ATTR_WIDTH: channel.width,
            ATTR_HEIGHT: channel.height,
            ATTR_FPS: channel.fps,
            ATTR_BITRATE: channel.bitrate,
            ATTR_CHANNEL_ID: channel.id,
        }

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the Camera Image."""
        # Without a stream the camera is rendered by rapidly polling snapshots;
        # request low quality then to avoid hammering the console with large
        # images. width/height are unused (the public endpoint has no resize).
        high_quality = None if self._stream_source else False
        self._last_image = await self.device.get_public_api_snapshot(
            high_quality=high_quality, package=self.channel.is_package
        )
        return self._last_image

    @override
    async def stream_source(self) -> str | None:
        """Return the Stream Source."""
        return self._stream_source

    @async_ufp_instance_command
    @override
    async def async_enable_motion_detection(self) -> None:
        """Call the job and enable motion detection."""
        await self.device.set_motion_detection(True)

    @async_ufp_instance_command
    @override
    async def async_disable_motion_detection(self) -> None:
        """Call the job and disable motion detection."""
        await self.device.set_motion_detection(False)
