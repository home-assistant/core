"""Support for Eufy Security cameras."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time
from typing import Any
from urllib.parse import quote as url_quote

from aiohttp import ClientError
from eufy_security import Camera, EufySecurityError

from homeassistant.components.camera import (
    Camera as CameraEntity,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_HARDWARE_VERSION,
    ATTR_IP_ADDRESS,
    ATTR_SERIAL_NUMBER,
    ATTR_SOFTWARE_VERSION,
    ATTR_STATION_SERIAL,
)
from .coordinator import EufySecurityConfigEntry, EufySecurityCoordinator
from .entity import EufySecurityEntity, exception_wrap

_LOGGER = logging.getLogger(__name__)

# Minimum seconds between RTSP snapshot captures to avoid overwhelming cameras
SNAPSHOT_THROTTLE_SECONDS = 60

# Coordinator handles updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EufySecurityCameraEntityDescription(CameraEntityDescription):
    """Describes Eufy Security camera entity."""


CAMERA_DESCRIPTION = EufySecurityCameraEntityDescription(
    key="camera",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufySecurityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eufy Security cameras from a config entry."""
    data = entry.runtime_data
    coordinator = data.coordinator

    known_cameras: set[str] = set()

    @callback
    def _check_new_cameras() -> None:
        """Check for new cameras and add them."""
        cameras = coordinator.data.get("cameras", {})
        new_cameras = set(cameras.keys()) - known_cameras
        if new_cameras:
            known_cameras.update(new_cameras)
            async_add_entities(
                EufySecurityCamera(coordinator, cameras[serial], CAMERA_DESCRIPTION)
                for serial in new_cameras
            )

    # Add initial cameras
    for camera in data.devices.get("cameras", {}).values():
        known_cameras.add(camera.serial)
    async_add_entities(
        EufySecurityCamera(coordinator, camera, CAMERA_DESCRIPTION)
        for camera in data.devices.get("cameras", {}).values()
    )

    # Listen for new cameras added after setup
    entry.async_on_unload(coordinator.async_add_listener(_check_new_cameras))


class EufySecurityCamera(EufySecurityEntity, CameraEntity):
    """Representation of a Eufy Security camera."""

    entity_description: EufySecurityCameraEntityDescription

    def __init__(
        self,
        coordinator: EufySecurityCoordinator,
        camera: Camera,
        description: EufySecurityCameraEntityDescription,
    ) -> None:
        """Initialize the camera."""
        super().__init__(coordinator, camera)
        CameraEntity.__init__(self)
        self.entity_description = description
        self._attr_unique_id = f"{camera.serial}-{description.key}"
        self._attr_name = None  # Use device name only
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._stream_url: str | None = None
        self._last_image: bytes | None = None
        self._last_snapshot_time: float = 0
        self._snapshot_lock = asyncio.Lock()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        cameras = self.coordinator.data.get("cameras", {})
        if self._camera.serial in cameras:
            self._camera = cameras[self._camera.serial]
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs: dict[str, Any] = {
            ATTR_SERIAL_NUMBER: self._camera.serial,
            ATTR_STATION_SERIAL: self._camera.station_serial,
            ATTR_HARDWARE_VERSION: self._camera.hardware_version,
            ATTR_SOFTWARE_VERSION: self._camera.software_version,
        }
        if self._camera.ip_address:
            attrs[ATTR_IP_ADDRESS] = self._camera.ip_address
        return attrs

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        # Try cloud thumbnail first (lightweight, no camera impact)
        image_url = self._camera.last_camera_image_url
        if image_url:
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        self._last_image = await response.read()
                        return self._last_image
            except ClientError:
                pass  # Fall through to RTSP or cached image

        # Fall back to capturing frame from RTSP stream (if credentials configured)
        # Use throttling to avoid overwhelming the camera with connections
        rtsp_url = self._get_rtsp_url()
        if rtsp_url:
            now = time.monotonic()
            time_since_last = now - self._last_snapshot_time

            # Only capture if enough time has passed and we're not already capturing
            if time_since_last >= SNAPSHOT_THROTTLE_SECONDS:
                if self._snapshot_lock.locked():
                    # Another capture is in progress, return cached image
                    return self._last_image

                async with self._snapshot_lock:
                    # Double-check timing after acquiring lock
                    now = time.monotonic()
                    if now - self._last_snapshot_time >= SNAPSHOT_THROTTLE_SECONDS:
                        image = await self._async_get_image_from_stream(rtsp_url)
                        if image:
                            self._last_image = image
                            self._last_snapshot_time = now

        return self._last_image

    def _get_rtsp_url(self) -> str | None:
        """Build RTSP URL for local streaming if credentials are configured."""
        if (
            self._camera.ip_address
            and self._camera.rtsp_username
            and self._camera.rtsp_password
        ):
            username = url_quote(self._camera.rtsp_username, safe="")
            password = url_quote(self._camera.rtsp_password, safe="")
            return f"rtsp://{username}:{password}@{self._camera.ip_address}:554/live0"
        return None

    async def _async_get_image_from_stream(self, stream_url: str) -> bytes | None:
        """Capture a single frame from the RTSP stream using ffmpeg."""
        ffmpeg_manager = get_ffmpeg_manager(self.hass)
        ffmpeg_binary = ffmpeg_manager.binary

        # Build ffmpeg command to capture one frame as JPEG
        # Use short timeout to fail fast if camera doesn't respond
        command = [
            ffmpeg_binary,
            "-rtsp_transport",
            "tcp",
            "-timeout",
            "5000000",  # 5 second timeout in microseconds
            "-i",
            stream_url,
            "-frames:v",
            "1",
            "-f",
            "image2",
            "-c:v",
            "mjpeg",
            "-q:v",
            "2",
            "pipe:1",
        ]

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=8.0)

            if process.returncode == 0 and stdout:
                _LOGGER.debug(
                    "Camera %s captured frame: %d bytes",
                    self._camera.name,
                    len(stdout),
                )
                return stdout

            # Log stderr only at debug level to reduce noise
            if stderr and b"404" not in stderr:
                _LOGGER.debug(
                    "Camera %s ffmpeg failed (code %s)",
                    self._camera.name,
                    process.returncode,
                )
        except TimeoutError:
            _LOGGER.debug(
                "Timeout capturing frame from camera %s",
                self._camera.name,
            )
            # Kill the process if it's still running
            if process and process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass
        except OSError as err:
            _LOGGER.debug(
                "Failed to capture frame from camera %s: %s",
                self._camera.name,
                err,
            )

        return None

    @exception_wrap
    async def stream_source(self) -> str | None:
        """Return the source of the stream.

        Prefers local RTSP streaming when credentials are configured.
        Falls back to cloud streaming if local RTSP is not available.
        """
        # Always prefer local RTSP if credentials are configured
        # Generate fresh each time since IP could have changed
        local_rtsp = self._get_rtsp_url()
        if local_rtsp:
            return local_rtsp

        # Fall back to cloud streaming (cached to avoid repeated API calls)
        if self._stream_url is None:
            _LOGGER.debug("Starting cloud stream for camera %s", self._camera.name)
            self._stream_url = await self._camera.async_start_stream()
        return self._stream_url

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        await super().async_will_remove_from_hass()
        if self._stream_url is not None:
            try:
                await self._camera.async_stop_stream()
            except EufySecurityError:
                _LOGGER.debug(
                    "Failed to stop stream for camera %s",
                    self._camera.name,
                )
            self._stream_url = None
