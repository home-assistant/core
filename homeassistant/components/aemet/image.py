"""Support for the AEMET OpenData images."""

from __future__ import annotations

from typing import Final

from aemet_opendata.const import AOD_DATETIME, AOD_IMG_BYTES, AOD_IMG_TYPE, AOD_RADAR
from aemet_opendata.helpers import dict_nested_value

from homeassistant.components.image import Image, ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AemetConfigEntry, WeatherUpdateCoordinator
from .entity import AemetEntity

AEMET_IMAGES: Final[tuple[ImageEntityDescription, ...]] = (
    ImageEntityDescription(
        key=AOD_RADAR,
        translation_key="weather_radar",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AemetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AEMET OpenData image entities based on a config entry."""
    domain_data = config_entry.runtime_data
    name = domain_data.name
    coordinator = domain_data.coordinator

    unique_id = config_entry.unique_id
    assert unique_id is not None

    async_add_entities(
        AemetImage(
            hass,
            name,
            coordinator,
            description,
            unique_id,
        )
        for description in AEMET_IMAGES
        if dict_nested_value(coordinator.data["lib"], [description.key]) is not None
    )


class AemetImage(AemetEntity, ImageEntity):
    """Implementation of an AEMET OpenData image."""

    entity_description: ImageEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        coordinator: WeatherUpdateCoordinator,
        description: ImageEntityDescription,
        unique_id: str,
    ) -> None:
        """Initialize the image."""
        super().__init__(coordinator, name, unique_id)
        ImageEntity.__init__(self, hass)
        self.entity_description = description
        self._attr_unique_id = f"{unique_id}-{description.key}"

        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update image attributes."""
        image_data = self.get_aemet_value([self.entity_description.key])
        self._cached_image = Image(
            content_type=image_data.get(AOD_IMG_TYPE),
            content=image_data.get(AOD_IMG_BYTES),
        )
        self._attr_image_last_updated = image_data.get(AOD_DATETIME)
