"""Support for Ubiquiti's UniFi Protect NVR.

Camera entities use the public API (get_rtsps_streams) exclusively for obtaining
RTSPS stream URLs. This provides stable stream URLs that work
reliably with Home Assistant's stream integration.
"""

from __future__ import annotations

from collections.abc import Generator
import logging

from uiprotect.data import (
    Camera as UFPCamera,
    CameraChannel,
    ProtectAdoptableDeviceModel,
    StateType,
)
from uiprotect.exceptions import ClientError, NotAuthorized, NvrError

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

# Mapping of channel IDs to quality names for the public API (get_rtsps_streams)
# The public API returns stream URLs by quality name, not by channel ID
CHANNEL_ID_TO_QUALITY: dict[int, str] = {
    0: "high",
    1: "medium",
    2: "low",
    3: "package",
}


@callback
def _create_rtsp_repair(
    hass: HomeAssistant, entry: UFPConfigEntry, data: ProtectData, camera: UFPCamera
) -> None:
    edit_key = "readonly"
    if camera.can_write(data.api.bootstrap.auth_user):
        edit_key = "writable"

    translation_key = f"rtsp_disabled_{edit_key}"
    issue_key = f"rtsp_disabled_{camera.id}"

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_key,
        is_fixable=True,
        is_persistent=False,
        learn_more_url="https://www.home-assistant.io/integrations/unifiprotect/#camera-streams",
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={"camera": camera.display_name},
        data={"entry_id": entry.entry_id, "camera_id": camera.id},
    )


@callback
def _get_camera_channels(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    data: ProtectData,
    ufp_device: UFPCamera | None = None,
) -> Generator[tuple[UFPCamera, CameraChannel, bool]]:
    """Get all the camera channels.

    Creates camera entities for all available channels (high, medium, low, package).
    Stream availability is determined by the public API at runtime.
    """
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

        is_default = True
        for channel in camera.channels:
            # Package channel is created if available, but disabled by default
            if channel.is_package:
                yield camera, channel, False
            # For regular channels, create entities for all known quality levels
            elif channel.id in CHANNEL_ID_TO_QUALITY:
                yield camera, channel, is_default
                is_default = False


def _async_camera_entities(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    data: ProtectData,
    ufp_device: UFPCamera | None = None,
) -> list[ProtectDeviceEntity]:
    disable_stream = data.disable_stream
    entities: list[ProtectDeviceEntity] = []
    for camera, channel, is_default in _get_camera_channels(
        hass, entry, data, ufp_device
    ):
        # do not enable streaming for package camera
        # 2 FPS causes a lot of buffering
        entities.append(
            ProtectCamera(
                data,
                camera,
                channel,
                is_default,
                disable_stream or channel.is_package,
            )
        )
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
        if not isinstance(device, UFPCamera):
            return
        async_add_entities(_async_camera_entities(hass, entry, data, ufp_device=device))

    data.async_subscribe_adopt(_add_new_device)
    entry.async_on_unload(
        async_dispatcher_connect(hass, data.channels_signal, _add_new_device)
    )
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

    @property
    def _rtsp_issue_id(self) -> str:
        """Return the repair issue ID for RTSP disabled."""
        return f"rtsp_disabled_{self.device.id}"

    @property
    def _should_stream(self) -> bool:
        """Return whether streaming should be attempted."""
        return not self._disable_stream and self._quality is not None

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
        self._quality = CHANNEL_ID_TO_QUALITY.get(channel.id)
        super().__init__(data, camera)
        device = self.device

        self._attr_unique_id = f"{device.mac}_{channel.id}"
        self._attr_name = get_camera_base_name(channel)
        # only the default (first) channel is enabled by default
        self._attr_entity_registry_enabled_default = is_default
        # Set the stream source before finishing the init
        # because async_added_to_hass is too late and camera
        # integration uses async_internal_added_to_hass to access
        # the stream source which is called before async_added_to_hass
        self._async_set_stream_source()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        # Listen for stream cache invalidation signals
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.data.streams_signal, self._async_handle_streams_signal
            )
        )
        # Fetch or create RTSPS streams from public API
        await self._async_refresh_rtsps_streams()

    @callback
    def _async_handle_streams_signal(self, camera_id: str | None = None) -> None:
        """Handle streams signal - refresh if our camera is affected."""
        if camera_id is None or camera_id == self.device.id:
            self.hass.async_create_task(
                self._async_refresh_rtsps_streams(), eager_start=True
            )

    async def _async_refresh_rtsps_streams(self) -> None:
        """Refresh RTSPS streams from cache or API."""
        if not self._should_stream:
            # Delete any existing repair issue if streaming is disabled
            ir.async_delete_issue(self.hass, DOMAIN, self._rtsp_issue_id)
            return

        # Type narrowing - _should_stream ensures _quality is not None
        quality = self._quality
        assert quality is not None

        # Check if camera has been checked during setup (pre-fetched sequentially)
        if self.data.is_camera_rtsps_checked(self.device.id):
            cached_streams = self.data.get_camera_rtsps_streams(self.device.id)
            if cached_streams is not None and cached_streams.get_stream_url(quality):
                self._async_set_stream_source()
                self.async_write_ha_state()
                ir.async_delete_issue(self.hass, DOMAIN, self._rtsp_issue_id)
            else:
                # No streams or this quality not available - create repair
                self._maybe_create_rtsp_repair()
            return

        # Not yet checked - fetch from API (individual camera refresh after signal)
        try:
            streams = await self.device.get_rtsps_streams()
            self.data.set_camera_rtsps_streams(self.device.id, streams)
            if streams is not None and streams.get_stream_url(quality):
                self._async_set_stream_source()
                self.async_write_ha_state()
                ir.async_delete_issue(self.hass, DOMAIN, self._rtsp_issue_id)
            else:
                self._maybe_create_rtsp_repair()
        except NotAuthorized:
            _LOGGER.warning(
                "Cannot fetch RTSPS streams without API key, streaming will be disabled"
            )
            # Mark as checked to prevent repeated API calls
            self.data.set_camera_rtsps_streams(self.device.id, None)
        except (ClientError, NvrError):
            _LOGGER.exception("Error fetching RTSPS streams from public API")
            # Mark as checked to prevent repeated API calls
            self.data.set_camera_rtsps_streams(self.device.id, None)

    @callback
    def _maybe_create_rtsp_repair(self) -> None:
        """Create RTSP repair issue if applicable."""
        if not self.device.is_third_party_camera and not self.data.disable_stream:
            _create_rtsp_repair(
                self.hass,
                self.data.config_entry,
                self.data,
                self.device,
            )

    @callback
    def _async_set_stream_source(self) -> None:
        """Set stream source from public API cache."""
        if not self._should_stream:
            self._attr_supported_features = _DISABLE_FEATURE
            self._stream_source = None
            return

        # Type narrowing - _should_stream ensures _quality is not None
        quality = self._quality
        assert quality is not None

        # Use public API URL from central RTSPS streams cache
        cached_streams = self.data.get_camera_rtsps_streams(self.device.id)
        if cached_streams is not None:
            stream_url = cached_streams.get_stream_url(quality)
            if stream_url is not None:
                self._attr_supported_features = _ENABLE_FEATURE
                self._stream_source = stream_url
                return

        # No public API stream available
        self._attr_supported_features = _DISABLE_FEATURE
        self._stream_source = None

    @callback
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

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the Camera Image."""
        if self.channel.is_package:
            last_image = await self.device.get_package_snapshot(width, height)
        else:
            last_image = await self.device.get_public_api_snapshot()
        self._last_image = last_image
        return self._last_image

    async def stream_source(self) -> str | None:
        """Return the Stream Source."""
        return self._stream_source

    @async_ufp_instance_command
    async def async_enable_motion_detection(self) -> None:
        """Call the job and enable motion detection."""
        await self.device.set_motion_detection(True)

    @async_ufp_instance_command
    async def async_disable_motion_detection(self) -> None:
        """Call the job and disable motion detection."""
        await self.device.set_motion_detection(False)
