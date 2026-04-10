"""Support for Eufy Security cameras."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any
from urllib.parse import quote as url_quote

from eufy_security import Camera, EufySecurityError

from homeassistant.components.camera import (
    Camera as CameraEntity,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
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

    _attr_use_stream_for_stills = True

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
        attrs[ATTR_IP_ADDRESS] = self._camera.ip_address
        return attrs

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
