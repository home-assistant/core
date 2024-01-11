"""Support for Roborock image."""
import asyncio
import io
from itertools import chain

from roborock import RoborockCommand
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Sizes
from vacuum_map_parser_roborock.map_data_parser import RoborockMapDataParser

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import DOMAIN, IMAGE_CACHE_INTERVAL, IMAGE_DRAWABLES, MAP_SLEEP
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock image platform."""

    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities = list(
        chain.from_iterable(
            await asyncio.gather(
                *(create_coordinator_maps(coord) for coord in coordinators.values())
            )
        )
    )
    async_add_entities(entities)


class RoborockMap(RoborockCoordinatedEntity, ImageEntity):
    """A class to let you visualize the map."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        map_flag: int,
        starting_map: bytes,
        map_name: str,
    ) -> None:
        """Initialize a Roborock map."""
        RoborockCoordinatedEntity.__init__(self, unique_id, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_name = map_name
        self.parser = RoborockMapDataParser(
            ColorsPalette(), Sizes(), IMAGE_DRAWABLES, ImageConfig(), []
        )
        self._attr_image_last_updated = dt_util.utcnow()
        self.map_flag = map_flag
        self.cached_map = self._create_image(starting_map)

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return diagnostic entity category for any non-selected maps."""
        if not self.is_selected:
            return EntityCategory.DIAGNOSTIC
        return None

    @property
    def is_selected(self) -> bool:
        """Return if this map is the currently selected map."""
        return self.map_flag == self.coordinator.current_map

    def is_map_valid(self) -> bool:
        """Update this map if it is the current active map, and the vacuum is cleaning."""
        return (
            self.is_selected
            and self.image_last_updated is not None
            and self.coordinator.roborock_device_info.props.status is not None
            and bool(self.coordinator.roborock_device_info.props.status.in_cleaning)
        )

    def _handle_coordinator_update(self):
        # Bump last updated every third time the coordinator runs, so that async_image
        # will be called and we will evaluate on the new coordinator data if we should
        # update the cache.
        if (
            dt_util.utcnow() - self.image_last_updated
        ).total_seconds() > IMAGE_CACHE_INTERVAL and self.is_map_valid():
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Update the image if it is not cached."""
        if self.is_map_valid():
            map_data: bytes = await self.cloud_api.get_map_v1()
            self.cached_map = self._create_image(map_data)
        return self.cached_map

    def _create_image(self, map_bytes: bytes) -> bytes:
        """Create an image using the map parser."""
        parsed_map = self.parser.parse(map_bytes)
        if parsed_map.image is None:
            raise HomeAssistantError("Something went wrong creating the map.")
        img_byte_arr = io.BytesIO()
        parsed_map.image.data.save(img_byte_arr, format="PNG")
        return img_byte_arr.getvalue()


async def create_coordinator_maps(
    coord: RoborockDataUpdateCoordinator,
) -> list[RoborockMap]:
    """Get the starting map information for all maps for this device. The following steps must be done synchronously.

    Only one map can be loaded at a time per device.
    """
    entities = []
    maps = await coord.cloud_api.get_multi_maps_list()
    if maps is not None and maps.map_info is not None:
        cur_map = coord.current_map
        # This won't be None at this point as the coordinator will have run first.
        assert cur_map is not None
        # Sort the maps so that we start with the current map and we can skip the
        # load_multi_map call.
        maps_info = sorted(
            maps.map_info, key=lambda data: data.mapFlag == cur_map, reverse=True
        )
        for roborock_map in maps_info:
            # Load the map - so we can access it with get_map_v1
            if roborock_map.mapFlag != cur_map:
                # Only change the map and sleep if we have multiple maps.
                await coord.api.send_command(
                    RoborockCommand.LOAD_MULTI_MAP, [roborock_map.mapFlag]
                )
                # We cannot get the map until the roborock servers fully process the
                # map change.
                await asyncio.sleep(MAP_SLEEP)
            # Get the map data
            api_data: bytes = await coord.cloud_api.get_map_v1()
            entities.append(
                RoborockMap(
                    f"{slugify(coord.roborock_device_info.device.duid)}_map_{roborock_map.name}",
                    coord,
                    roborock_map.mapFlag,
                    api_data,
                    roborock_map.name,
                )
            )
        if len(maps.map_info) != 1:
            # Set the map back to the map the user previously had selected so that it
            # does not change the end user's app.
            # Only needs to happen when we changed maps above.
            await coord.cloud_api.send_command(
                RoborockCommand.LOAD_MULTI_MAP, [cur_map]
            )
    return entities
