"""Entity for Fyta plant image."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FytaConfigEntry, FytaCoordinator
from .entity import FytaPlantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FytaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the FYTA plant images."""
    coordinator = entry.runtime_data

    description = ImageEntityDescription(key="plant_image")

    async_add_entities(
        FytaPlantImageEntity(coordinator, entry, description, plant_id)
        for plant_id in coordinator.fyta.plant_list
        if plant_id in coordinator.data
    )

    def _async_add_new_device(plant_id: int) -> None:
        async_add_entities(
            [FytaPlantImageEntity(coordinator, entry, description, plant_id)]
        )

    coordinator.new_device_callbacks.append(_async_add_new_device)


class FytaPlantImageEntity(FytaPlantEntity, ImageEntity):
    """Represents a Fyta image."""

    entity_description: ImageEntityDescription

    def __init__(
        self,
        coordinator: FytaCoordinator,
        entry: ConfigEntry,
        description: ImageEntityDescription,
        plant_id: int,
    ) -> None:
        """Initiatlize Fyta Image entity."""
        super().__init__(coordinator, entry, description, plant_id)
        ImageEntity.__init__(self, coordinator.hass)

        self._attr_name = None

    @property
    def image_url(self) -> str:
        """Return the image_url for this sensor."""
        image = self.plant.plant_origin_path
        if image != self._attr_image_url:
            self._attr_image_last_updated = datetime.now()

        return image
