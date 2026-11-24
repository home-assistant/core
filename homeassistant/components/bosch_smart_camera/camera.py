"""Camera platform for the Bosch Smart Camera integration."""

from typing import override

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoschCameraConfigEntry, BoschCameraCoordinator
from .entity import BoschCameraEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschCameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the cameras of the account."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_cameras() -> None:
        # Forget removed cameras so one that comes back gets a new entity.
        known.intersection_update(coordinator.data)
        new = set(coordinator.data) - known
        known.update(new)
        async_add_entities(BoschCamera(coordinator, camera_id) for camera_id in new)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_cameras))
    _add_new_cameras()


class BoschCamera(BoschCameraEntity, Camera):
    """A camera of the account, showing the image of its latest event."""

    _attr_name = None

    def __init__(self, coordinator: BoschCameraCoordinator, camera_id: str) -> None:
        """Initialize the camera."""
        super().__init__(coordinator, camera_id)
        Camera.__init__(self)
        self._attr_unique_id = camera_id

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the image of the latest event."""
        return await self.coordinator.async_get_snapshot(self._camera_id)

    @property
    @override
    def available(self) -> bool:
        """Return whether the camera is part of the latest camera list."""
        return super().available and self._camera_id in self.coordinator.data
