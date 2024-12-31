"""Camera for the Trafikverket Camera integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.const import ATTR_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TVCameraConfigEntry
from .const import ATTR_DESCRIPTION, ATTR_TYPE
from .coordinator import TVDataUpdateCoordinator
from .entity import TrafikverketCameraEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TVCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Trafikverket Camera."""

    coordinator = entry.runtime_data

    async_add_entities(
        [
            TVCamera(
                coordinator,
                entry.entry_id,
            )
        ],
    )


class TVCamera(TrafikverketCameraEntity, Camera):
    """Implement Trafikverket camera."""

    _unrecorded_attributes = frozenset({ATTR_DESCRIPTION, ATTR_LOCATION})

    _attr_name = None
    _attr_translation_key = "tv_camera"
    coordinator: TVDataUpdateCoordinator

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the camera."""
        super().__init__(coordinator, entry_id)
        Camera.__init__(self)
        self._attr_unique_id = entry_id

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera picture."""
        return self.coordinator.data.image

    @property
    def is_on(self) -> bool:
        """Return camera on."""
        return self.coordinator.data.data.active is True

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes."""
        return {
            ATTR_DESCRIPTION: self.coordinator.data.data.description,
            ATTR_LOCATION: self.coordinator.data.data.location,
            ATTR_TYPE: self.coordinator.data.data.camera_type,
        }
