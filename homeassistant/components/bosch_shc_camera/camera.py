"""Camera platform for the Bosch Smart Home Camera integration."""

from typing import override

from bosch_shc_camera_client.cameras import Camera as CameraData, CameraModel

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_flow import DOMAIN
from .coordinator import BoschCameraConfigEntry, BoschCameraCoordinator

PARALLEL_UPDATES = 0

MODEL_NAMES = {
    CameraModel.EYES_OUTDOOR: "Eyes Outdoor",
    CameraModel.INDOOR_360: "360° Indoor",
    CameraModel.EYES_OUTDOOR_II: "Eyes Outdoor II",
    CameraModel.EYES_INDOOR_II: "Eyes Indoor II",
}


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


class BoschCamera(CoordinatorEntity[BoschCameraCoordinator], Camera):
    """A camera of the account, without stream or snapshot support yet."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: BoschCameraCoordinator, camera_id: str) -> None:
        """Initialize the camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._camera_id = camera_id
        self._attr_unique_id = camera_id
        data = self._camera_data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_id)},
            manufacturer="Bosch",
            model=MODEL_NAMES.get(data.model, data.hardware_version or None),
            name=data.title,
            sw_version=data.firmware_version,
        )

    @property
    def _camera_data(self) -> CameraData:
        """Return the latest data of this camera."""
        return self.coordinator.data[self._camera_id]

    @property
    @override
    def available(self) -> bool:
        """Return whether the camera is part of the latest camera list."""
        return super().available and self._camera_id in self.coordinator.data
