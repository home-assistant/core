"""Support for Roborock image."""

from datetime import datetime
import logging

from roborock.devices.traits.v1.home import HomeTrait
from roborock.devices.traits.v1.map_content import MapContent

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import (
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
    RoborockDataUpdateCoordinator,
)
from .entity import RoborockCoordinatedEntityB01Q10, RoborockCoordinatedEntityV1

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
                coord,
                coord.properties_api.home,
                map_info.map_flag,
                map_info.name,
            )
            for coord in config_entry.runtime_data.v1
            if coord.properties_api.home is not None
            for map_info in (coord.properties_api.home.home_map_info or {}).values()
        ),
    )
    async_add_entities(
        RoborockQ10Map(coordinator)
        for coordinator in config_entry.runtime_data.b01_q10
    )


class RoborockMap(RoborockCoordinatedEntityV1, ImageEntity):
    """A class to let you visualize the map."""

    _attr_has_entity_name = True
    image_last_updated: datetime
    _attr_name: str

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: RoborockDataUpdateCoordinator,
        home_trait: HomeTrait,
        map_flag: int,
        map_name: str,
    ) -> None:
        """Initialize a Roborock map."""
        map_name = map_name or f"Map {map_flag}"
        # Note: Map names are not a valid unique id since they can be changed
        # in the roborock app. This should be migrated to use map flag for
        # the unique id.
        unique_id = f"{coordinator.duid_slug}_map_{map_name}"
        RoborockCoordinatedEntityV1.__init__(self, unique_id, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self.config_entry = config_entry
        self._attr_name = map_name
        self._home_trait = home_trait
        self.map_flag = map_flag
        self.cached_map: bytes | None = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_image_last_updated = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass load any previously cached maps from disk."""
        await super().async_added_to_hass()
        self._attr_image_last_updated = self.coordinator.last_home_update
        self.async_write_ha_state()

    @property
    def _map_content(self) -> MapContent | None:
        if self._home_trait.home_map_content and (
            map_content := self._home_trait.home_map_content.get(self.map_flag)
        ):
            return map_content
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        If the coordinator has updated the map, we can update the image.
        """
        if self.coordinator.data is None or (map_content := self._map_content) is None:
            return
        if self.cached_map != map_content.image_content:
            self.cached_map = map_content.image_content
            self._attr_image_last_updated = self.coordinator.last_home_update
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Get the cached image."""
        if (map_content := self._map_content) is None:
            raise HomeAssistantError("Map flag not found in coordinator maps")
        return map_content.image_content


class RoborockQ10Map(RoborockCoordinatedEntityB01Q10, ImageEntity):
    """A class to visualize the Q10 map.

    The Q10 exposes a single push-driven map per device (multi-map selection is
    not reachable on this channel). The rendered PNG is read from the ``map``
    trait and refreshed whenever the pushed image bytes change.
    """

    _attr_translation_key = "map"
    _attr_content_type = "image/png"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    coordinator: RoborockB01Q10UpdateCoordinator

    def __init__(self, coordinator: RoborockB01Q10UpdateCoordinator) -> None:
        """Initialize a Roborock Q10 map."""
        RoborockCoordinatedEntityB01Q10.__init__(
            self, f"map_{coordinator.duid_slug}", coordinator
        )
        ImageEntity.__init__(self, coordinator.hass)
        self._cached_map = coordinator.api.map.image_content
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_added_to_hass(self) -> None:
        """Register a trait listener for push-based map updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.api.map.add_update_listener(self._handle_map_update)
        )

    @callback
    def _handle_map_update(self) -> None:
        """Bump the image timestamp when the pushed map bytes change."""
        image_content = self.coordinator.api.map.image_content
        if self._cached_map != image_content:
            self._cached_map = image_content
            self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return the current rendered map image."""
        return self.coordinator.api.map.image_content
