"""Image platform for Immich Frames."""

from datetime import datetime
from typing import Any, override
from urllib.parse import quote

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ImmichFramesConfigEntry, ImmichFramesDataUpdateCoordinator
from .entity import ImmichFramesEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichFramesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the frame image."""
    async_add_entities([ImmichFrameImage(entry.runtime_data)])


class ImmichFrameImage(ImmichFramesEntity, ImageEntity):
    """Display the current image selected from Immich."""

    _attr_has_entity_name = True
    _attr_translation_key = "image"
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator: ImmichFramesDataUpdateCoordinator) -> None:
        """Initialize the image entity."""
        ImmichFramesEntity.__init__(self, coordinator, "image")
        ImageEntity.__init__(self, coordinator.hass)

    @property
    @override
    def image_last_updated(self) -> datetime | None:
        """Return the selected asset update time."""
        data = self.coordinator.current_data
        return (
            data.updated_at
            if self.coordinator.parent_available
            and data
            and data.connected
            and data.status == "ready"
            else None
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the selected asset link."""
        data = self.coordinator.current_data
        if (
            not self.coordinator.parent_available
            or data is None
            or not data.connected
            or data.status != "ready"
        ):
            return {}
        base_url = self.coordinator.configuration_url
        if base_url is None:
            return {}
        asset_id = quote(data.asset.asset_id, safe="")
        return {"open_in_immich": f"{base_url}/photos/{asset_id}"}

    @override
    async def async_image(self) -> bytes | None:
        """Return the selected Immich image."""
        data = self.coordinator.current_data
        return (
            data.image
            if self.coordinator.parent_available
            and data
            and data.connected
            and data.status == "ready"
            else None
        )
