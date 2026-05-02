"""
WJG Camera Entity
=================
Stellt Livestream (RTSP) und Snapshot für HA zur Verfügung.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, MANUFACTURER, MODEL
from .coordinator import WJGCameraCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: WJGCameraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WJGCamera(coordinator, entry)])

class WJGCamera(  # pyright: ignore[reportArgumentType]
    CoordinatorEntity[WJGCameraCoordinator],
    Camera,
):
    """Kamera-Entity für WJG XM-3820."""

    _attr_has_entity_name = True
    _attr_name = None  # Gerätename als Entity-Name

    def __init__(
        self, coordinator: WJGCameraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        Camera.__init__(self)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_camera"
        self._attr_supported_features = (
            CameraEntityFeature.STREAM | CameraEntityFeature.ON_OFF
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"WJG {MODEL}",
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=(
                f"http://{self.coordinator.host}:{self.coordinator.http_port}"
            ),
        )

    @property
    def available(self) -> bool:
        return bool(
            super().available and self.coordinator.data
            and self.coordinator.data.get("available", False)
        )

    @property
    def is_recording(self) -> bool:
        return self.coordinator.is_recording

    @property
    def motion_detection_enabled(self) -> bool:
        return True

    async def stream_source(self) -> str | None:
        """RTSP-Stream-URL zurückgeben."""
        return self.coordinator.rtsp_url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Aktuelles Standbild laden."""
        # Bevorzuge gecachten Snapshot aus Coordinator
        if self.coordinator.data and "snapshot_bytes" in self.coordinator.data:
            return self.coordinator.data["snapshot_bytes"]
        return await self.coordinator.async_snapshot()

    async def async_enable_motion_detection(self) -> None:
        """Bewegungserkennung aktivieren."""
        _LOGGER.info("Bewegungserkennung aktiviert")
        return None

    async def async_disable_motion_detection(self) -> None:
        """Bewegungserkennung deaktivieren."""
        _LOGGER.info("Bewegungserkennung deaktiviert")
        return None

    async def async_turn_on(self) -> None:
        """Kamera-Stream einschalten (IR-LEDs etc.)."""
        return None

    async def async_turn_off(self) -> None:
        """Kamera-Stream ausschalten."""
        return None

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        raise NotImplementedError()

    def enable_motion_detection(self) -> None:
        raise NotImplementedError()

    def disable_motion_detection(self) -> None:
        raise NotImplementedError()

    def turn_on(self) -> None:
        raise NotImplementedError()

    def turn_off(self) -> None:
        raise NotImplementedError()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute für HA."""
        return {
            "rtsp_url": self.coordinator.rtsp_url,
            "snapshot_url": self.coordinator.snapshot_url,
            "host": self.coordinator.host,
            "protocol": self.coordinator.protocol,
        }
