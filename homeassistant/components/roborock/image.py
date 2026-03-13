"""Support for Roborock image."""

from __future__ import annotations

from datetime import datetime
import io
import logging

from PIL import Image, UnidentifiedImageError
from roborock.devices.traits.v1.home import HomeTrait
from roborock.devices.traits.v1.map_content import MapContent

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_MAP_ROTATION,
    DEFAULT_MAP_ROTATION,
    MAP_ROTATION_OPTIONS,
)
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
        # Map names are not a valid unique id since they can be changed in the Roborock app.
        # This should be migrated to use map flag for the unique id.
        unique_id = f"{coordinator.duid_slug}_map_{map_name}"
        RoborockCoordinatedEntityV1.__init__(self, unique_id, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self.config_entry = config_entry
        self._attr_name = map_name
        self._home_trait = home_trait
        self.map_flag = map_flag
        self.cached_map: bytes | None = None

        # Rotated image cache (invalidated when map content changes)
        self._rotated_cache: bytes | None = None
        self._rotated_cache_rotation: int | None = None

        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
        """
        if (map_content := self._map_content) is None:
            return
        if self.cached_map != map_content.image_content:
            self.cached_map = map_content.image_content

            # Invalidate rotated cache on new map content
            self._rotated_cache = None
            self._rotated_cache_rotation = None

            self._attr_image_last_updated = self.coordinator.last_home_update

        super()._handle_coordinator_update()

    def _rotate_image(self, raw: bytes, rotation: int) -> bytes:
        """Rotate image in executor thread."""
        img = Image.open(io.BytesIO(raw))
        img = img.rotate(rotation, expand=True)

        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    
    async def async_image(self) -> bytes | None:
        """Return the map image."""
        if (map_content := self._map_content) is None:
            raise HomeAssistantError("Map flag not found in coordinator maps")

        raw = map_content.image_content

        raw_rotation = self.config_entry.options.get(
            CONF_MAP_ROTATION, DEFAULT_MAP_ROTATION
        )

        try:
            rotation = int(raw_rotation)
        except (TypeError, ValueError):
            _LOGGER.debug(
                "Invalid map rotation value %s, falling back to %s",
                raw_rotation,
                DEFAULT_MAP_ROTATION,
            )
            rotation = DEFAULT_MAP_ROTATION

        if rotation not in MAP_ROTATION_OPTIONS:
            _LOGGER.debug(
                "Unsupported map rotation %s, allowed values: %s, falling back to %s",
                rotation,
                MAP_ROTATION_OPTIONS,
                DEFAULT_MAP_ROTATION,
            )
            rotation = DEFAULT_MAP_ROTATION

        if rotation == DEFAULT_MAP_ROTATION:
            return raw
        
        if (
            self._rotated_cache is not None
            and self._rotated_cache_rotation == rotation
        ):
            return self._rotated_cache

        try:
            rotated = await self.hass.async_add_executor_job(
                self._rotate_image, raw, rotation
            )

            self._rotated_cache = rotated
            self._rotated_cache_rotation = rotation

            return rotated

        except (OSError, UnidentifiedImageError) as err:
            _LOGGER.debug(
                "Failed to rotate Roborock map image: %s, returning original image",
                err,
            )
            self._rotated_cache = None
            self._rotated_cache_rotation = None
            return raw
        