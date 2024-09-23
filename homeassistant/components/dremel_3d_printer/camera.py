"""Support for Dremel 3D45 Camera."""

from __future__ import annotations

from homeassistant.components.camera import CameraEntityDescription
from homeassistant.components.mjpeg import MjpegCamera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import Dremel3DPrinterDataUpdateCoordinator, DremelConfigEntry
from .entity import Dremel3DPrinterEntity

CAMERA_TYPE = CameraEntityDescription(
    key="camera",
    name="Camera",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DremelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a MJPEG IP Camera for the 3D45 Model. The 3D20 and 3D40 models don't have built in cameras."""
    async_add_entities([Dremel3D45Camera(config_entry.runtime_data, CAMERA_TYPE)])


class Dremel3D45Camera(Dremel3DPrinterEntity, MjpegCamera):
    """Dremel 3D45 Camera."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        description: CameraEntityDescription,
    ) -> None:
        """Initialize a new Dremel 3D Printer integration camera for the 3D45 model."""
        super().__init__(coordinator, description)
        MjpegCamera.__init__(
            self,
            mjpeg_url=coordinator.api.get_stream_url(),
            still_image_url=coordinator.api.get_snapshot_url(),
        )
