"""Image platform for Immich Frames."""

from datetime import datetime
from typing import Any, override
from urllib.parse import quote

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ImmichFramesDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[ImmichFramesDataUpdateCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the frame image."""
    async_add_entities([ImmichFrameImage(entry.runtime_data)])


class ImmichFrameImage(
    CoordinatorEntity[ImmichFramesDataUpdateCoordinator], ImageEntity
):
    """Display the current image selected from Immich."""

    _attr_has_entity_name = True
    _attr_translation_key = "image"
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator: ImmichFramesDataUpdateCoordinator) -> None:
        """Initialize the image entity."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_image"

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the frame device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=self.coordinator.config_entry.title,
            manufacturer="Immich",
            model="Photo frame",
            configuration_url=self.coordinator.immich_entry.runtime_data.configuration_url,
        )

    @property
    @override
    def image_last_updated(self) -> datetime:
        """Return the selected asset update time."""
        return self.coordinator.data.updated_at

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the selected asset link."""
        base_url = self.coordinator.immich_entry.runtime_data.configuration_url
        asset_id = quote(self.coordinator.data.asset.asset_id, safe="")
        return {"open_in_immich": f"{base_url}/photos/{asset_id}"}

    @override
    async def async_image(self) -> bytes | None:
        """Return the selected Immich image."""
        return self.coordinator.data.image
