"""Support for Roborock image."""

from datetime import datetime
import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RoborockConfigEntry, RoborockDataUpdateCoordinator
from .entity import RoborockCoordinatedEntityV1

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock image platform."""

    async_add_entities(
        (
            RoborockMap(
                config_entry,
                f"{coord.duid_slug}_map_{map_info.name}",
                coord,
                map_info.flag,
                map_info.name,
            )
            for coord in config_entry.runtime_data.v1
            for map_info in coord.maps.values()
        ),
    )


class RoborockMap(RoborockCoordinatedEntityV1, ImageEntity):
    """A class to let you visualize the map."""

    _attr_has_entity_name = True
    image_last_updated: datetime
    _attr_name: str

    def __init__(
        self,
        config_entry: ConfigEntry,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        map_flag: int,
        map_name: str,
    ) -> None:
        """Initialize a Roborock map."""
        RoborockCoordinatedEntityV1.__init__(self, unique_id, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self.config_entry = config_entry
        self._attr_name = map_name
        self.map_flag = map_flag
        self.cached_map = b""
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_selected(self) -> bool:
        """Return if this map is the currently selected map."""
        return self.map_flag == self.coordinator.current_map

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass load any previously cached maps from disk."""
        await super().async_added_to_hass()
        self._attr_image_last_updated = self.coordinator.maps[
            self.map_flag
        ].last_updated
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        # If the coordinator has updated the map, we can update the image.
        self._attr_image_last_updated = self.coordinator.maps[
            self.map_flag
        ].last_updated

        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Get the cached image."""
        return self.coordinator.maps[self.map_flag].image
