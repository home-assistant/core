"""Support for INDI Allsky camera."""

from typing import Any, override

from aioindiallsky import IndiAllSkyError

from homeassistant.components.camera import Camera
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

    _attr_translation_key = "camera"

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
            return image

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return camera extra state attributes."""
        exposure = self.coordinator.data.exposure
        if exposure is None:
            return None

        return {
            "binmode": exposure.binmode,
            "exposure": exposure.exposure,
            "filename": exposure.filename,
            "gain": exposure.gain,
            "night": exposure.night,
            "sqm": exposure.sqm,
            "stars": exposure.stars,
            "temperature": exposure.temp,
        }
