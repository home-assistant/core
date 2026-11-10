"""Image platform for SMHI integration."""

from datetime import datetime
from typing import override

from homeassistant.components.image import ImageEntity
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SMHIConfigEntry, SMHIRadarDataUpdateCoordinator
from .entity import SmhiEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SMHIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SMHI image platform."""
    location = entry.data[CONF_LOCATION]
    async_add_entities(
        [
            SMHIRadarImage(
                location[CONF_LATITUDE],
                location[CONF_LONGITUDE],
                coordinator=entry.runtime_data.radar_coordinator,
            )
        ]
    )


class SMHIRadarImage(SmhiEntity[SMHIRadarDataUpdateCoordinator], ImageEntity):
    """Representation of a SMHI radar image."""

    _attr_content_type = "image/png"
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "radar"
    _image: bytes | None = None
    _image_valid_time: datetime | None = None

    def __init__(
        self,
        latitude: str,
        longitude: str,
        coordinator: SMHIRadarDataUpdateCoordinator,
    ) -> None:
        """Initiate SMHI radar image."""
        super().__init__(latitude, longitude, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_unique_id = f"{latitude}, {longitude}-radar"

    @override
    def update_entity_data(self) -> None:
        """Refresh the entity data."""
        self._attr_image_last_updated = self.coordinator.data["valid_time"]

    @override
    async def async_image(self) -> bytes | None:
        """Return the radar image, drawn once per radar update."""
        valid_time = self.coordinator.data["valid_time"]
        if self._image is None or self._image_valid_time != valid_time:
            self._image = await self.coordinator.async_get_image()
            self._image_valid_time = valid_time
        return self._image
