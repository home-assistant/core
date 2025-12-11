"""Support for Eufy Security cameras."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from aiohttp import ClientError

from homeassistant.components.camera import (
    Camera as CameraEntity,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Camera, EufySecurityError
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
    translation_key="camera",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufySecurityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eufy Security cameras from a config entry."""
    data = entry.runtime_data
    coordinator = data.coordinator

    async_add_entities(
        EufySecurityCamera(coordinator, camera, CAMERA_DESCRIPTION)
        for camera in data.devices.get("cameras", {}).values()
    )


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
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._stream_url: str | None = None
        self._last_image: bytes | None = None

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
        return {
            "serial_number": self._camera.serial,
            "station_serial": self._camera.station_serial,
            "hardware_version": self._camera.hardware_version,
            "software_version": self._camera.software_version,
        }

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if self._camera.last_camera_image_url:
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(self._camera.last_camera_image_url) as response:
                    if response.status == 200:
                        self._last_image = await response.read()
            except ClientError:
                _LOGGER.debug(
                    "Failed to fetch camera image for %s",
                    self._camera.name,
                )
        return self._last_image

    @exception_wrap
    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        if self._stream_url is None:
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
