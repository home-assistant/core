"""Support for Roborock image."""

from datetime import datetime
import logging
from typing import override

from roborock.devices.traits.v1.home import HomeTrait
from roborock.devices.traits.v1.map_content import MapContent

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import (
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
    RoborockCoordinatorType,
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
    coordinators = config_entry.runtime_data

    @callback
    def async_add_coordinator_entities(
        coordinator: RoborockCoordinatorType,
    ) -> None:
        """Add entities for a specific coordinator."""
        if isinstance(coordinator, RoborockDataUpdateCoordinator):
            map_entities: dict[int, RoborockMap] = {}

            @callback
            def async_update_map_entities() -> None:
                """Add new map entities and remove deleted ones."""
                if (map_infos := coordinator.properties_api.home.home_map_info) is None:
                    return
                current_flags = set(map_infos.keys())
                existing_flags = set(map_entities.keys())

                # Add new maps
                new_entities = []
                for map_flag in current_flags - existing_flags:
                    map_info = map_infos[map_flag]
                    entity = RoborockMap(
                        config_entry,
                        coordinator,
                        coordinator.properties_api.home,
                        map_info.map_flag,
                        map_info.name,
                    )
                    map_entities[map_flag] = entity
                    new_entities.append(entity)
                if new_entities:
                    async_add_entities(new_entities)

                # Remove deleted maps
                entity_registry = er.async_get(coordinator.hass)
                for map_flag in existing_flags - current_flags:
                    entity = map_entities.pop(map_flag)
                    coordinator.hass.async_create_task(entity.async_remove())
                    if entity.entity_id and entity_registry.async_get(entity.entity_id):
                        entity_registry.async_remove(entity.entity_id)

            async_update_map_entities()

            config_entry.async_on_unload(
                coordinator.properties_api.home.add_update_listener(
                    async_update_map_entities
                )
            )
        elif isinstance(coordinator, RoborockB01Q10UpdateCoordinator):
            async_add_entities([RoborockMapQ10(coordinator)])

    for coordinator in coordinators.values():
        async_add_coordinator_entities(coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"roborock_coordinator_added_{config_entry.entry_id}",
            async_add_coordinator_entities,
        )
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

    @override
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
    @override
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

    @override
    async def async_image(self) -> bytes | None:
        """Get the cached image."""
        if (map_content := self._map_content) is None:
            raise HomeAssistantError("Map flag not found in coordinator maps")
        return map_content.image_content


class RoborockMapQ10(RoborockCoordinatedEntityB01Q10, ImageEntity):
    """A class to let you visualize the current map of a Q10 device.

    The Q10 pushes its current map over MQTT rather than serving it on
    request, and the multi-map list is not reachable on this channel, so the
    device exposes a single push-driven map entity.
    """

    _attr_content_type = "image/png"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "map"

    def __init__(self, coordinator: RoborockB01Q10UpdateCoordinator) -> None:
        """Initialize a Roborock Q10 map."""
        RoborockCoordinatedEntityB01Q10.__init__(
            self, f"map_{coordinator.duid_slug}", coordinator
        )
        ImageEntity.__init__(self, coordinator.hass)
        self._map_trait = coordinator.api.map
        self._cached_map: bytes | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Register a trait listener for push-based map updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._map_trait.add_update_listener(self._handle_map_update)
        )
        # Pick up a map that was pushed before the entity was added.
        self._handle_map_update()

    @callback
    def _handle_map_update(self) -> None:
        """Cache the newly pushed map if its content changed."""
        image_content = self._map_trait.image_content
        if image_content is None or image_content == self._cached_map:
            return
        self._cached_map = image_content
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    @override
    async def async_image(self) -> bytes | None:
        """Get the cached image."""
        return self._cached_map
