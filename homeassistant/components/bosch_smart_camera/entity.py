"""Base entity for the Bosch Smart Camera integration."""

from bosch_shc_camera_client.cameras import Camera as CameraData, CameraModel

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschCameraCoordinator

MODEL_NAMES = {
    CameraModel.EYES_OUTDOOR: "Eyes Outdoor",
    CameraModel.INDOOR_360: "360° Indoor",
    CameraModel.EYES_OUTDOOR_II: "Eyes Outdoor II",
    CameraModel.EYES_INDOOR_II: "Eyes Indoor II",
}


class BoschCameraEntity(CoordinatorEntity[BoschCameraCoordinator]):
    """Base class of the entities of a camera."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BoschCameraCoordinator, camera_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._camera_id = camera_id
        data = self._camera_data
        # Every platform describes the device, as any of them may be added first.
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
