"""Camera platform for reCamera Pro."""

import asyncio
from functools import cache
from pathlib import Path
import time
from typing import override

from recamera_protocol import RecameraError

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RecameraConfigEntry, RecameraCoordinator
from .entity import RecameraEntity, recamera_service_error

PARALLEL_UPDATES = 0
_STILL_CACHE_MAX_AGE_SECONDS = 1.0
_STILL_FAILURE_COOLDOWN_SECONDS = 0.5
_STREAM_OFF_IMAGE_PATH = Path(__file__).parent / "assets" / "stream_off.jpg"


@cache
def _load_stream_off_image() -> bytes | None:
    """Load the static placeholder JPEG shown when RTSP is disabled."""
    try:
        return _STREAM_OFF_IMAGE_PATH.read_bytes()
    except OSError:
        return None


async def _async_get_stream_image(
    camera: Camera,
    width: int | None = None,
    height: int | None = None,
    wait_for_next_keyframe: bool = False,
) -> bytes | None:
    """Return a still image from the camera's stream."""
    if (provider := camera.webrtc_provider) and (
        image := await provider.async_get_image(camera, width=width, height=height)
    ) is not None:
        return image
    if not camera.stream and CameraEntityFeature.STREAM in camera.supported_features:
        camera.stream = await camera.async_create_stream()
    if camera.stream:
        return await camera.stream.async_get_image(
            width=width,
            height=height,
            wait_for_next_keyframe=wait_for_next_keyframe,
        )
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RecameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up low-bandwidth and high-quality camera entities."""
    coordinator: RecameraCoordinator = config_entry.runtime_data
    async_add_entities(
        [
            RecameraSubstreamCamera(coordinator),
            RecameraMainstreamCamera(coordinator),
        ]
    )


class RecameraCamera(RecameraEntity, Camera):
    """Base entity for one reCamera Pro RTSP stream."""

    _attr_supported_features = CameraEntityFeature.STREAM | CameraEntityFeature.ON_OFF
    _stream_id: str
    _unique_suffix: str

    def __init__(self, coordinator: RecameraCoordinator) -> None:
        """Initialize one camera stream."""
        RecameraEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{coordinator.device_id}_{self._unique_suffix}"
        self._still_cache: bytes | None = None
        self._still_cached_at = 0.0
        self._still_cache_key: tuple[int | None, int | None] | None = None
        self._still_failure_key: tuple[int | None, int | None] | None = None
        self._still_failure_until = 0.0
        self._still_lock = asyncio.Lock()
        self._connection_generation = coordinator.connection_generation
        self._was_on = self.is_on
        self._stream_enabled_at = 0.0
        self._unsub_stream_stop: object | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Register pre-disable stream cleanup with the coordinator."""
        await super().async_added_to_hass()
        register = getattr(self.coordinator, "register_stream_stop_callback", None)
        if callable(register):
            self._unsub_stream_stop = register(
                self._stream_id,
                self._async_reset_media_after_host_change,
            )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister stream cleanup and stop any active stream worker."""
        unsub = getattr(self, "_unsub_stream_stop", None)
        if callable(unsub):
            unsub()
        self._unsub_stream_stop = None
        await self._async_drop_stream()
        await super().async_will_remove_from_hass()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Reset media objects after host change or stream toggle."""
        was_on = getattr(self, "_was_on", True)
        currently_on = self.is_on
        turned_off = was_on and not currently_on
        turned_on = not was_on and currently_on
        self._was_on = currently_on
        if turned_on:
            self._stream_enabled_at = time.monotonic()
            self._still_failure_key = None
            self._still_failure_until = 0.0
        if self._take_connection_generation_change() or turned_off or turned_on:
            self._still_cache = None
            self._still_cache_key = None
            self._still_failure_key = None
            self._still_failure_until = 0.0
            self.hass.async_create_background_task(
                self._async_reset_media_after_host_change(),
                f"{self.entity_id}.media-reset",
            )
        super()._handle_coordinator_update()

    def _take_connection_generation_change(self) -> bool:
        """Return whether the device connection address changed."""
        generation = self.coordinator.connection_generation
        if generation == self._connection_generation:
            return False
        self._connection_generation = generation
        return True

    async def _async_drop_stream(self) -> None:
        """Stop and clear the cached HA stream worker before retrying."""
        stream = self.stream
        self.stream = None
        if stream is not None:
            await stream.stop()

    async def _async_reset_media_after_host_change(self) -> None:
        """Drop consumers that still reference the previous device address."""
        self._still_cache = None
        self._still_cache_key = None
        self._still_failure_key = None
        self._still_failure_until = 0.0
        await self._async_drop_stream()

    @property
    @override
    def available(self) -> bool:
        """Return whether the camera device is reachable."""
        return bool(self.coordinator.last_update_success)

    @property
    @override
    def is_on(self) -> bool:
        """Return whether RTSP streaming is enabled for this camera."""
        coordinator = getattr(self, "coordinator", None)
        if coordinator is None:
            return True
        is_enabled = getattr(coordinator, "is_stream_enabled", None)
        if callable(is_enabled):
            return bool(is_enabled(self._stream_id))
        return coordinator.get_stream_url(self._stream_id) is not None

    @property
    @override
    def motion_detection_enabled(self) -> bool:
        """Return the motion-detect App lifecycle state."""
        return bool(
            self.coordinator.data is not None and self.coordinator.data.motion.running
        )

    @override
    async def async_turn_on(self) -> None:
        """Enable RTSP streaming for this camera stream."""
        try:
            await self.coordinator.async_set_stream_enabled(self._stream_id, True)
        except RecameraError as err:
            raise recamera_service_error(err) from err
        self._was_on = True
        self._stream_enabled_at = time.monotonic()
        self._still_failure_key = None
        self._still_failure_until = 0.0

    @override
    async def async_turn_off(self) -> None:
        """Disable RTSP streaming for this camera stream and drop media consumers."""
        try:
            await self.coordinator.async_set_stream_enabled(self._stream_id, False)
        except RecameraError as err:
            raise recamera_service_error(err) from err
        await self._async_reset_media_after_host_change()

    @override
    async def async_enable_motion_detection(self) -> None:
        """Enable the device-side motion-detect App."""
        try:
            await self.coordinator.async_set_motion_detection(True)
        except RecameraError as err:
            raise recamera_service_error(err) from err

    @override
    async def async_disable_motion_detection(self) -> None:
        """Disable the device-side motion-detect App."""
        try:
            await self.coordinator.async_set_motion_detection(False)
        except RecameraError as err:
            raise recamera_service_error(err) from err

    @property
    @override
    def use_stream_for_stills(self) -> bool:
        """Serve cached stills instead of starting a new keyframe wait."""
        return False

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        """Expose the current stream identity, codec, and RTSP state."""
        data = self.coordinator.data
        profile = (
            data.media_profiles.get(self._stream_id, {}) if data is not None else {}
        )
        codec = (profile.get("encode") or {}).get("sOutputDataType")
        return {
            "stream_id": self._stream_id,
            "codec": codec,
            "rtsp_enabled": self.is_on,
        }

    @override
    async def stream_source(self) -> str | None:
        """Return the selected device stream URL."""
        return self.coordinator.get_stream_url(self._stream_id)

    async def _async_stream_off_image(self) -> bytes | None:
        """Return the offline placeholder without blocking the event loop."""
        if _load_stream_off_image.cache_info().currsize > 0:
            return _load_stream_off_image()
        if self.hass is not None:
            return await self.hass.async_add_executor_job(_load_stream_off_image)
        return _load_stream_off_image()

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a current still or the offline placeholder when RTSP is off."""
        if not self.is_on:
            return await self._async_stream_off_image()
        return await self._async_refresh_still(width, height)

    async def _async_refresh_still(
        self,
        width: int | None,
        height: int | None,
    ) -> bytes | None:
        """Refresh the cached JPEG without duplicate concurrent work."""
        key = (width, height)
        now = time.monotonic()
        if self._still_failure_key == key and now < self._still_failure_until:
            return self._still_cache if self._still_cache_key == key else None
        if (
            self._still_cache is not None
            and self._still_cache_key == key
            and time.monotonic() - self._still_cached_at <= _STILL_CACHE_MAX_AGE_SECONDS
        ):
            return self._still_cache
        async with self._still_lock:
            if (
                self._still_cache is not None
                and self._still_cache_key == key
                and time.monotonic() - self._still_cached_at
                <= _STILL_CACHE_MAX_AGE_SECONDS
            ):
                return self._still_cache
            warming_up = (
                time.monotonic() - getattr(self, "_stream_enabled_at", 0.0) <= 8.0
            )
            max_attempts = 3 if warming_up else 1
            image: bytes | None = None
            for attempt in range(max_attempts):
                try:
                    image = await _async_get_stream_image(
                        self,
                        width=width,
                        height=height,
                        wait_for_next_keyframe=(attempt > 0),
                    )
                except TimeoutError, HomeAssistantError, OSError:
                    if attempt + 1 < max_attempts:
                        await self._async_drop_stream()
                        await asyncio.sleep(0.8)
                        continue
                    self._still_failure_key = key
                    self._still_failure_until = (
                        time.monotonic() + _STILL_FAILURE_COOLDOWN_SECONDS
                    )
                    raise
                if image:
                    break
                if attempt + 1 < max_attempts:
                    await self._async_drop_stream()
                    await asyncio.sleep(0.8)
            if image:
                self._still_cache = image
                self._still_cache_key = key
                self._still_cached_at = time.monotonic()
                self._still_failure_key = None
                self._still_failure_until = 0.0
                return image
            self._still_failure_key = key
            self._still_failure_until = (
                time.monotonic() + _STILL_FAILURE_COOLDOWN_SECONDS
            )
            return None


class RecameraSubstreamCamera(RecameraCamera):
    """Expose the low-bandwidth sub-stream."""

    _attr_translation_key = "live"
    _stream_id = "sub"
    _unique_suffix = "sub"


class RecameraMainstreamCamera(RecameraCamera):
    """Expose the high-quality main stream for the separate main view."""

    _attr_translation_key = "main"
    _attr_entity_registry_enabled_default = False
    _stream_id = "main"
    _unique_suffix = "main"
