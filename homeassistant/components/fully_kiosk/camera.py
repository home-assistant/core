"""Support for Fully Kiosk Browser camera."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fullykiosk import FullyKiosk

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


@dataclass(frozen=True, kw_only=True)
class FullyCameraEntityDescription(CameraEntityDescription):
    """Fully Kiosk Browser camera entity description."""

    image_action: Callable[[FullyKiosk], Any]
    on_action: Callable[[FullyKiosk], Any] | None
    off_action: Callable[[FullyKiosk], Any] | None
    is_on_fn: Callable[[dict[str, Any]], Any]


CAMERAS: tuple[FullyCameraEntityDescription, ...] = (
    FullyCameraEntityDescription(
        key="camera",
        translation_key="camera",
        image_action=lambda fully: fully.getCamshot(),
        on_action=lambda fully: fully.enableMotionDetection(),
        off_action=lambda fully: fully.disableMotionDetection(),
        is_on_fn=lambda data: data["settings"].get("motionDetection"),
    ),
    FullyCameraEntityDescription(
        key="screenshot",
        translation_key="screenshot",
        image_action=lambda fully: fully.getScreenshot(),
        on_action=None,
        off_action=None,
        is_on_fn=lambda data: True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the cameras."""
    coordinator: FullyKioskDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FullyCameraEntity(coordinator, description) for description in CAMERAS
    )


class FullyCameraEntity(FullyKioskEntity, Camera):
    """Fully Kiosk Browser camera entity."""

    entity_description: FullyCameraEntityDescription

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        description: FullyCameraEntityDescription,
    ) -> None:
        """Initialize the camera."""
        FullyKioskEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{coordinator.data['deviceID']}-{description.key}"
        self.entity_description = description
        if description.on_action:
            self._attr_supported_features = CameraEntityFeature.ON_OFF

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        return await self.entity_description.image_action(self.coordinator.fully)

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        if self.entity_description.on_action:
            await self.entity_description.on_action(self.coordinator.fully)
            await self.coordinator.async_refresh()

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        if self.entity_description.off_action:
            await self.entity_description.off_action(self.coordinator.fully)
            await self.coordinator.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = bool(self.entity_description.is_on_fn(self.coordinator.data))
        self.async_write_ha_state()
