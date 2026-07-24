"""Image platform for the Data Grand Lyon integration."""

from typing import override

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import SUBENTRY_TYPE_STOP
from .coordinator import DataGrandLyonConfigEntry, DataGrandLyonPictogramCoordinator
from .entity import DataGrandLyonStopPictogramEntity

PARALLEL_UPDATES = 0

IMAGE_DESCRIPTION = ImageEntityDescription(
    key="line_pictogram",
    translation_key="line_pictogram",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DataGrandLyonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Data Grand Lyon image entities."""
    pictogram_coordinator = entry.runtime_data.pictogram_coordinator

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STOP):
        async_add_entities(
            [
                DataGrandLyonStopImage(
                    pictogram_coordinator, subentry, IMAGE_DESCRIPTION, hass
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class DataGrandLyonStopImage(DataGrandLyonStopPictogramEntity, ImageEntity):
    """Image of the TCL line pictogram for a stop."""

    _attr_content_type = "image/svg+xml"
    _last_seen: bytes | None = None

    def __init__(
        self,
        coordinator: DataGrandLyonPictogramCoordinator,
        subentry: ConfigSubentry,
        description: ImageEntityDescription,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, subentry, description)
        ImageEntity.__init__(self, hass)

    @property
    def _pictogram(self) -> bytes | None:
        """Return the current pictogram bytes, or None if unavailable."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._subentry_id)

    @override
    async def async_added_to_hass(self) -> None:
        """Set the initial update time once the entity is registered."""
        self._last_seen = self._pictogram
        self._attr_image_last_updated = dt_util.utcnow()
        await super().async_added_to_hass()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update the timestamp when the pictogram bytes change."""
        if self._pictogram != self._last_seen:
            self._last_seen = self._pictogram
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    @override
    async def async_image(self) -> bytes | None:
        """Return the SVG pictogram bytes."""
        return self._pictogram
