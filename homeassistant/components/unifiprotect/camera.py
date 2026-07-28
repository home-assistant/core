"""Support for Ubiquiti's UniFi Protect NVR."""

from collections.abc import Iterable
import logging
from typing import cast, override

from uiprotect.data import (
    Camera as UFPCamera,
    ChannelQuality,
    DeviceState,
    ModelType,
    ProtectAdoptableDeviceModel,
    PublicDeviceModel,
    StateType,
    channel_id_for_quality,
)
from uiprotect.data.public_devices import PublicCamera

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_platform,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity

from .const import (
    ATTR_BITRATE,
    ATTR_CHANNEL_ID,
    ATTR_FPS,
    ATTR_HEIGHT,
    ATTR_WIDTH,
    DEFAULT_BRAND,
    DOMAIN,
)
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity
from .utils import async_ufp_instance_command, get_camera_base_name

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

# Main (non-package) RTSPS quality tiers, in default-preference order.
_MAIN_QUALITIES = (
    ChannelQuality.HIGH,
    ChannelQuality.MEDIUM,
    ChannelQuality.LOW,
)


@callback
def _create_rtsp_repair(
    hass: HomeAssistant, entry: UFPConfigEntry, public: PublicCamera
) -> None:
    # Keyed on the public camera: the fix flow verifies and creates the stream
    # through the public API, so it works without a private session too.
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"rtsp_disabled_{public.id}",
        is_fixable=True,
        is_persistent=False,
        learn_more_url="https://www.home-assistant.io/integrations/unifiprotect/#camera-streams",
        severity=IssueSeverity.WARNING,
        translation_key="rtsp_disabled",
        translation_placeholders={"camera": public.display_name},
        data={"entry_id": entry.entry_id, "camera_id": public.id},
    )


@callback
def _async_camera_entities(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    data: ProtectData,
    ufp_device: UFPCamera | None = None,
    public_device: PublicCamera | None = None,
) -> list[ProtectDeviceEntity]:
    """Create camera entities, enumerated public-master from ``PublicCamera``.

    Stream URLs come from the public API because it carries the authoritative
    per-camera host (stacked consoles resolve correctly), SRTP-stripped for
    go2rtc.
    """
    disable_stream = data.disable_stream
    entities: list[ProtectDeviceEntity] = []

    # Public-master enumeration: iterate the public camera list; the private
    # camera is paired by shared id (fill) and is None in public-only mode.
    pairs: Iterable[tuple[PublicCamera | None, UFPCamera | None]]
    if public_device is not None:
        private = (
            None
            if data.api.is_public_only
            else data.api.bootstrap.cameras.get(public_device.id)
        )
        # mirror the startup enumeration's adopted filter
        if private is not None and not private.is_adopted_by_us:
            return entities
        pairs = [(public_device, private)]
    elif ufp_device is None:
        pairs = data.get_public_cameras()
    else:
        adopted = data.async_get_public_device(ufp_device)
        pairs = [(adopted if isinstance(adopted, PublicCamera) else None, ufp_device)]

    for public, camera in pairs:
        # A just-adopted camera not yet mirrored into the public bootstrap is
        # deferred and picked up when enumeration re-runs.
        if public is None:
            if camera is not None:
                _LOGGER.debug(
                    "Deferring camera %s until its public mirror arrives",
                    camera.display_name,
                )
                data.async_add_pending_camera_id(camera.id)
            continue

        # Hybrid: a camera not yet in the private bootstrap (adopt race) is
        # skipped rather than built private-less — the adopt dispatch creates
        # it with its private fill, which would otherwise collide on unique_id.
        if camera is None and not data.api.is_public_only:
            _LOGGER.debug(
                "Deferring camera %s until its private object is adopted",
                public.display_name,
            )
            continue

        streams = data.get_rtsps_streams(public.id)
        issue_id = f"rtsp_disabled_{public.id}"
        tiers = public.hardware_stream_qualities()
        main_qualities = [q for q in _MAIN_QUALITIES if q in tiers]
        has_package = ChannelQuality.PACKAGE in tiers
        if not main_qualities:
            # The library guarantees the three main tiers; a camera without any
            # is a broken contract — surface it loudly, but do not let one
            # camera abort enumeration for the rest.
            _LOGGER.warning(
                "Camera %s reports no main stream tiers (%s); skipping",
                public.display_name,
                tiers,
            )
            continue

        # Active stream tiers come from the public ``rtsps_streams`` object.
        active = set(streams.get_active_stream_qualities()) if streams else set()
        has_stream = False
        for quality in main_qualities:
            if quality in active:
                entities.append(
                    ProtectCamera(
                        data, public, camera, quality, not has_stream, disable_stream
                    )
                )
                has_stream = True

        # the package channel is a snapshot-first view (very low FPS); always
        # expose it (disabled by default), streaming only when its quality is active
        if has_package:
            entities.append(
                ProtectCamera(
                    data, public, camera, ChannelQuality.PACKAGE, False, disable_stream
                )
            )

        if has_stream:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue

        # no active main stream: expose the first main tier for snapshots
        entities.append(
            ProtectCamera(data, public, camera, main_qualities[0], True, disable_stream)
        )
        # no repair when the stream can't be enabled anyway: a disconnected
        # camera is streamless because it is offline, not because it needs one.
        # The fix flow runs entirely on the public API, so public-only cameras
        # get the repair too; third-party is only knowable with a private fill.
        if (
            disable_stream
            or public.state is not DeviceState.CONNECTED
            or (camera is not None and camera.is_third_party_camera)
        ):
            ir.async_delete_issue(hass, DOMAIN, issue_id)
        else:
            _create_rtsp_repair(hass, entry, public)
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Discover cameras on a UniFi Protect NVR."""
    data = entry.runtime_data
    platform = entity_platform.async_get_current_platform()

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel | PublicCamera) -> None:
        if isinstance(device, PublicCamera):
            entities = _async_camera_entities(hass, entry, data, public_device=device)
        else:
            # AiPort inherits from Camera but should not create camera entities
            if not isinstance(device, UFPCamera) or device.model is ModelType.AIPORT:
                return
            entities = _async_camera_entities(hass, entry, data, ufp_device=device)
        # A re-enumeration (deferred mirror, RTSPS prime) overlaps entities
        # that already exist; the platform errors on live duplicates rather
        # than deduplicating, so add only the missing ones.
        live = {e.unique_id for e in platform.entities.values()}
        async_add_entities([e for e in entities if e.unique_id not in live])

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
        # flips with the stream source (an RTSPS prime can be the only change)
        "_attr_supported_features",
    )

    def __init__(
        self,
        data: ProtectData,
        public: PublicCamera,
        private: UFPCamera | None,
        quality: ChannelQuality,
        is_default: bool,
        disable_stream: bool,
    ) -> None:
        """Initialize an UniFi camera.

        The public camera is the master; the private camera fills gaps the
        public API does not cover and is ``None`` in public-only mode.
        """
        self._public = public
        self._public_missing = False
        self._private = private
        self._quality = quality
        self._is_package = quality is ChannelQuality.PACKAGE
        self._channel_id = channel_id_for_quality(quality)
        self._disable_stream = disable_stream
        self._last_image: bytes | None = None
        # The base tracks the private device in hybrid (unchanged behaviour) and
        # the public device in public-only, so it always has a mac to key on.
        super().__init__(data, cast(ProtectDeviceType, private or public))
        self._attr_unique_id = f"{self.device.mac}_{self._channel_id}"
        self._attr_name = get_camera_base_name(quality)
        # only the default (first active) quality channel is enabled by default
        self._attr_entity_registry_enabled_default = is_default
        # Set the stream source before finishing the init
        # because async_added_to_hass is too late and camera
        # integration uses async_internal_added_to_hass to access
        # the stream source which is called before async_added_to_hass
        self._async_set_stream_source()

    @callback
    def _async_set_stream_source(self) -> None:
        """Set the public-API RTSPS stream URL (SRTP stripped for go2rtc)."""
        quality = self._quality
        streams = self.data.get_rtsps_streams(self._public.id)
        if self._disable_stream or streams is None:
            source = None
            if streams is None and not self._disable_stream and not self._is_package:
                # online camera unexpectedly absent from the public bootstrap;
                # log so this is distinguishable from an intentionally off stream
                _LOGGER.debug(
                    "No public RTSPS data for camera %s (%s); using snapshots",
                    self._public.name,
                    self._public.id,
                )
        else:
            source = streams.get_stream_url(quality, srtp=False)
        self._attr_supported_features = _ENABLE_FEATURE if source else _DISABLE_FEATURE
        self._stream_source = source

    @callback
    @override
    def _async_set_device_info(self) -> None:
        if self._private is not None:
            super()._async_set_device_info()
            return
        # public-only: no market_name/firmware_version/protect_url, and
        # ``type`` only on newer firmware, so device identity is limited. The
        # NVR link is omitted — an API-key-only client has no private
        # bootstrap to read the NVR mac from, and resolving it publicly is
        # async; the public-only config mode wires it at setup instead.
        public = self._public
        self._attr_device_info = DeviceInfo(
            name=public.display_name,
            model=public.type,
            manufacturer=DEFAULT_BRAND,
            connections={(dr.CONNECTION_NETWORK_MAC, public.mac)},
        )

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        if self._private is not None:
            super()._async_update_device_from_protect(device)
            updated_device = self.device
            # A poll/resync can replace the bootstrap objects; follow them so
            # commands and reads never act on a detached model.
            self._private = updated_device
            if isinstance(
                public := self.data.async_get_public_device(updated_device),
                PublicCamera,
            ):
                self._public = public
            else:
                # keep the last object for identity, but log so a vanished
                # public mirror is observable rather than a silent no-op
                _LOGGER.debug(
                    "Camera %s has no public mirror; keeping the last known one",
                    updated_device.display_name,
                )
            channel_id = self._channel_id
            channel = (
                updated_device.channels[channel_id]
                if channel_id is not None and channel_id < len(updated_device.channels)
                else None
            )
            if channel is None:
                # A tier without its private channel blanks the diagnostics;
                # log so a camera reconfiguration (or a quality that maps to no
                # channel) is distinguishable from a bug.
                _LOGGER.debug(
                    "Camera %s has no private channel %s; diagnostic attributes"
                    " unavailable",
                    updated_device.display_name,
                    channel_id,
                )
            motion_enabled = updated_device.recording_settings.enable_motion_detection
            self._attr_motion_detection_enabled = (
                motion_enabled if motion_enabled is not None else True
            )
            state_type_is_connected = updated_device.state is StateType.CONNECTED
            self._attr_is_recording = (
                state_type_is_connected and updated_device.is_recording
            )
            is_connected = self.data.last_update_success and state_type_is_connected
            # some cameras have detachable lens that could make them offline
            self._attr_available = is_connected and updated_device.is_video_ready

            self._async_set_stream_source()
            self._attr_extra_state_attributes = {
                ATTR_WIDTH: channel.width if channel else None,
                ATTR_HEIGHT: channel.height if channel else None,
                ATTR_FPS: channel.fps if channel else None,
                ATTR_BITRATE: channel.bitrate if channel else None,
                ATTR_CHANNEL_ID: channel_id,
            }
            return

        # public-only: recording/motion state and the per-stream diagnostics
        # have no public equivalent and degrade; availability tracks the public
        # devices websocket health and the public camera state.
        public = self._public
        self._attr_motion_detection_enabled = False
        self._attr_is_recording = False
        self._attr_available = (
            self.data.last_public_update_success
            and not self._public_missing
            and public.state is DeviceState.CONNECTED
        )
        self._async_set_stream_source()
        self._attr_extra_state_attributes = {
            ATTR_WIDTH: None,
            ATTR_HEIGHT: None,
            ATTR_FPS: None,
            ATTR_BITRATE: None,
            ATTR_CHANNEL_ID: self._channel_id,
        }

    @callback
    def _async_public_camera_updated(self, obj: PublicDeviceModel | None) -> None:
        """Handle a public devices websocket update for this camera.

        ``obj`` is the refreshed public object, or ``None`` for a websocket
        state change or an unmergeable frame, in which case it is re-read from
        the public bootstrap. A camera missing from the bootstrap on re-read
        has been removed and reads as unavailable until it reappears.
        """
        if obj is None:
            obj = self.data.async_get_public_device(self._public)
        if isinstance(obj, PublicCamera):
            self._public = obj
            self._public_missing = False
        else:
            self._public_missing = True
        device = (
            self._private
            if self._private is not None
            else cast(ProtectDeviceType, self._public)
        )
        self._async_updated_event(device)

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # The stream URLs live on the public camera and change outside the
        # private websocket (a background RTSPS prime announces itself on the
        # public channel), so every camera tracks its public mirror; in
        # public-only mode this is also the only state source.
        self.async_on_remove(
            self.data.async_subscribe_public(
                self._public.mac, self._async_public_camera_updated
            )
        )
        # A public update or delete can land between entity construction and
        # this subscription; re-read so the entity does not start stale.
        self._async_public_camera_updated(None)

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the Camera Image.

        While snapshot-polling (no stream) request low quality to avoid
        hammering the console. width/height are unused (the public endpoint
        has no resize).
        """
        # Inlines the library's device-level default (support_full_hd_snapshot
        # when streaming, low otherwise) since public-only has no private
        # device object; the resolved value is unchanged.
        high_quality = bool(
            self._stream_source and self._public.feature_flags.support_full_hd_snapshot
        )
        self._last_image = await self.data.api.get_public_api_camera_snapshot(
            camera_id=self._public.id,
            high_quality=high_quality,
            package=self._is_package,
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
        await self._async_set_motion_detection(True)

    @async_ufp_instance_command
    @override
    async def async_disable_motion_detection(self) -> None:
        """Call the job and disable motion detection."""
        await self._async_set_motion_detection(False)

    async def _async_set_motion_detection(self, enabled: bool) -> None:
        # the public API has no motion-detection setter; without a private
        # session the command cannot be sent and must not report success.
        if (private := self._private) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="motion_detection_public_only",
            )
        await private.set_motion_detection(enabled)
