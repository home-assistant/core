"""Support for Roborock image."""

from datetime import datetime, timedelta
import logging

from roborock.devices.traits.v1.home import HomeTrait
from roborock.devices.traits.v1.map_content import MapContent

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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


class RoborockMap(RoborockCoordinatedEntityV1, ImageEntity):
    """A class to let you visualize the map."""

    _attr_has_entity_name = True
    image_last_updated: datetime
    _attr_name: str

    # Minimum interval between state updates to prevent Activity spam (1 minute)
    MIN_STATE_UPDATE_INTERVAL = timedelta(minutes=1)

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
        # Track last state update time for debouncing (fixes #161039)
        self._last_state_update: datetime | None = None

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

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        If the coordinator has updated the map, we can update the image.
        Only trigger state changes when the actual map image changes
        to avoid flooding Activity with frequent map updates during cleaning.
        """
        if (map_content := self._map_content) is None:
            return

        # Check if the map image actually changed
        map_changed = self.cached_map != map_content.image_content

        if map_changed:
            self.cached_map = map_content.image_content
            self._attr_image_last_updated = self.coordinator.last_home_update

            # Apply debouncing to prevent spamming Activity with frequent updates
            now = datetime.utcnow()
            if (
                self._last_state_update is None
                or (now - self._last_state_update) >= self.MIN_STATE_UPDATE_INTERVAL
            ):
                # Only update state if enough time has passed
                super()._handle_coordinator_update()
                self._last_state_update = now
                _LOGGER.debug(
                    "Map %s updated at %s", self._attr_name, self._last_state_update
                )
            else:
                _LOGGER.debug(
                    "Map %s image updated but skipping state change "
                    "(debounce: %s since last update)",
                    self._attr_name,
                    now - self._last_state_update,
                )
        # Note: if no map change, we skip calling parent to avoid unnecessary state changes

    async def async_image(self) -> bytes | None:
        """Get the cached image."""
        if (map_content := self._map_content) is None:
            raise HomeAssistantError("Map flag not found in coordinator maps")
        return map_content.image_content
