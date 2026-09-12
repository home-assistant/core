"""Support for INDI Allsky camera."""

from typing import override

from aioindiallsky import IndiAllSkyError

from homeassistant.components.camera import Camera
from homeassistant.components.image import infer_image_type
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IndiAllSkyConfigEntry, IndiAllSkyDataUpdateCoordinator
from .entity import IndiAllSkyEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndiAllSkyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the INDI Allsky camera platform."""
    coordinator = entry.runtime_data
    async_add_entities([IndiAllSkyCamera(coordinator, entry)])


class IndiAllSkyCamera(IndiAllSkyEntity, Camera):
    """Representation of an INDI Allsky camera."""

    _attr_name = None

    def __init__(
        self,
        coordinator: IndiAllSkyDataUpdateCoordinator,
        entry: IndiAllSkyConfigEntry,
    ) -> None:
        """Initialize the camera."""
        super().__init__(coordinator, entry)
        Camera.__init__(self)
        self._attr_unique_id = entry.entry_id

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of current camera image."""
        try:
            image: bytes = await self.coordinator.client.fetch_image("latestimage")
        except IndiAllSkyError:
            return None
        else:
            if content_type := infer_image_type(image):
                self.content_type = content_type
            return image
