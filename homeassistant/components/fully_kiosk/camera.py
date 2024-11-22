"""Support for Fully Kiosk Browser camera."""

from __future__ import annotations

from fullykiosk import FullyKioskError

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FullyKioskConfigEntry
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FullyKioskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the cameras."""
    coordinator = entry.runtime_data
    async_add_entities([FullyCameraEntity(coordinator)])


class FullyCameraEntity(FullyKioskEntity, Camera):
    """Fully Kiosk Browser camera entity."""

    _attr_name = None
    _attr_supported_features = CameraEntityFeature.ON_OFF

    def __init__(self, coordinator: FullyKioskDataUpdateCoordinator) -> None:
        """Initialize the camera."""
        FullyKioskEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{coordinator.data['deviceID']}-camera"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        try:
            image_bytes: bytes = await self.coordinator.fully.getCamshot()
        except FullyKioskError as err:
            raise HomeAssistantError(err) from err
        else:
            return image_bytes

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        await self.coordinator.fully.enableMotionDetection()
        await self.coordinator.async_refresh()

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        await self.coordinator.fully.disableMotionDetection()
        await self.coordinator.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data["settings"].get("motionDetection")
        self.async_write_ha_state()
