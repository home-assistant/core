"""Entity for Fyta plant image."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.image import (
    Image,
    ImageEntity,
    ImageEntityDescription,
    valid_image_content_type,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FytaConfigEntry, FytaCoordinator
from .entity import FytaPlantEntity

_LOGGER = logging.getLogger(__name__)


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
        self._user_image: bool = coordinator.config_entry.options["user_image"]

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""

        if self._user_image:
            if self._cached_image is None:
                response = await self.coordinator.fyta.get_plant_image(
                    self.plant.user_picture_path
                )
                _LOGGER.debug("Response of downloading user image: %s", response)
                if response is None:
                    _LOGGER.debug(
                        "%s: Error getting new image from %s",
                        self.entity_id,
                        self.plant.user_picture_path,
                    )
                    return None

                content_type, raw_image = response
                self._cached_image = Image(
                    valid_image_content_type(content_type), raw_image
                )

            return self._cached_image.content

        return await ImageEntity.async_image(self)

    @property
    def image_url(self) -> str:
        """Return the image_url for this plant."""
        url = (
            self.plant.user_picture_path
            if self._user_image
            else self.plant.plant_origin_path
        )

        if url != self._attr_image_url:
            self._cached_image = None
            self._attr_image_last_updated = datetime.now()
        return url
