"""Camera entity for PrusaLink."""
from __future__ import annotations

from pyprusalink.types import NotFound

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, JobUpdateCoordinator, PrusaLinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PrusaLink camera."""
    coordinator: JobUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["job"]
    async_add_entities([PrusaLinkJobPreviewEntity(coordinator)])


class PrusaLinkJobPreviewEntity(PrusaLinkEntity, Camera):
    """Defines a PrusaLink camera."""

    last_path = ""
    last_path_no_thumbnail_available = ""
    last_image: bytes
    _attr_translation_key = "job_preview"

    def __init__(self, coordinator: JobUpdateCoordinator) -> None:
        """Initialize a PrusaLink camera entity."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{self.coordinator.config_entry.entry_id}_job_preview"

    @property
    def available(self) -> bool:
        """Get if camera is available."""
        return (
            super().available
            and (file := self.coordinator.data.get("file"))
            and (thumbnail := file.get("refs", {}).get("thumbnail"))
            and thumbnail != self.last_path_no_thumbnail_available
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera."""
        if not self.available:
            return None

        path = self.coordinator.data["file"]["refs"]["thumbnail"]

        if self.last_path_no_thumbnail_available == path:
            return None

        if self.last_path == path:
            return self.last_image

        try:
            self.last_image = await self.coordinator.api.get_file(path)
            self.last_path = path
        except NotFound:
            self.last_path_no_thumbnail_available = path
            return None
        except Exception as ex:
            raise ex

        return self.last_image
