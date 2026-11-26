"""Button platform for the Bosch Smart Camera integration."""

from typing import override

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoschCameraConfigEntry, BoschCameraCoordinator
from .entity import BoschCameraEntity

# Serialize the cloud writes.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschCameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the restart buttons of the cameras."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_cameras() -> None:
        # Forget removed cameras so one that comes back gets a new entity.
        known.intersection_update(coordinator.data)
        new = set(coordinator.data) - known
        known.update(new)
        async_add_entities(
            BoschRestartButton(coordinator, camera_id) for camera_id in new
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_new_cameras))
    _add_new_cameras()


class BoschRestartButton(BoschCameraEntity, ButtonEntity):
    """Restart of a camera."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    # A restart is disruptive, so the user opts in.
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BoschCameraCoordinator, camera_id: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, camera_id)
        self._attr_unique_id = f"{camera_id}_restart"

    @override
    async def async_press(self) -> None:
        """Restart the camera."""
        await self.coordinator.async_restart_camera(self._camera_id)
