"""Camera entity for PrusaLink."""

from dataclasses import dataclass

from pyprusalink.types import PrinterState

from homeassistant.components.camera import Camera, CameraEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PrusaLinkConfigEntry, PrusaLinkUpdateCoordinator
from .entity import PrusaLinkEntity, PrusaLinkEntityDescription


@dataclass(frozen=True, kw_only=True)
class PrusaLinkCameraEntityDescription(
    CameraEntityDescription, PrusaLinkEntityDescription
):
    """Describes PrusaLink camera entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrusaLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PrusaLink camera."""
    coordinator = entry.runtime_data["job"]
    async_add_entities([PrusaLinkJobPreviewEntity(coordinator)])


class PrusaLinkJobPreviewEntity(PrusaLinkEntity, Camera):
    """Defines a PrusaLink camera."""

    entity_description = PrusaLinkCameraEntityDescription(
        key="job_preview",
        translation_key="job_preview",
        available_fn=lambda data: bool(
            data.get("state") != PrinterState.IDLE.value
            and (file := data.get("file"))
            and file.get("refs", {}).get("thumbnail")
        ),
    )
    last_path = ""
    last_image: bytes

    def __init__(self, coordinator: PrusaLinkUpdateCoordinator) -> None:
        """Initialize a PrusaLink camera entity."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{self.coordinator.config_entry.entry_id}_job_preview"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera."""
        if not self.available:
            return None

        path = self.coordinator.data["file"]["refs"]["thumbnail"]

        if self.last_path == path:
            return self.last_image

        self.last_image = await self.coordinator.api.get_file(path)
        self.last_path = path
        return self.last_image
