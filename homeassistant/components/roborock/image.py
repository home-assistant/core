"""Support for Roborock image."""

import asyncio
from datetime import datetime
import io
from itertools import chain

from roborock import RoborockCommand
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Sizes
from vacuum_map_parser_roborock.map_data_parser import RoborockMapDataParser

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from . import RoborockConfigEntry
from .const import DEFAULT_DRAWABLES, DOMAIN, DRAWABLES, IMAGE_CACHE_INTERVAL, MAP_SLEEP
from .coordinator import RoborockDataUpdateCoordinator
from .entity import RoborockCoordinatedEntityV1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock image platform."""

    drawables = [
        drawable
        for drawable, default_value in DEFAULT_DRAWABLES.items()
        if config_entry.options.get(DRAWABLES, {}).get(drawable, default_value)
    ]
    entities = list(
        chain.from_iterable(
            await asyncio.gather(
                *(
                    create_coordinator_maps(coord, drawables)
                    for coord in config_entry.runtime_data.v1
                )
            )
        )
    )
    async_add_entities(entities)


class RoborockMap(RoborockCoordinatedEntityV1, ImageEntity):
    """A class to let you visualize the map."""

    _attr_has_entity_name = True
    image_last_updated: datetime

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        map_flag: int,
        starting_map: bytes,
        map_name: str,
        drawables: list[Drawable],
    ) -> None:
        """Initialize a Roborock map."""
        RoborockCoordinatedEntityV1.__init__(self, unique_id, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_name = map_name
        self.parser = RoborockMapDataParser(
            ColorsPalette(), Sizes(), drawables, ImageConfig(), []
        )
        self._attr_image_last_updated = dt_util.utcnow()
        self.map_flag = map_flag
        try:
            self.cached_map = self._create_image(starting_map)
        except HomeAssistantError:
            # If we failed to update the image on init,
            # we set cached_map to empty bytes
            # so that we are unavailable and can try again later.
            self.cached_map = b""
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        """Determines if the entity is available."""
        return self.cached_map != b""

    @property
    def is_selected(self) -> bool:
        """Return if this map is the currently selected map."""
        return self.map_flag == self.coordinator.current_map

    def is_map_valid(self) -> bool:
        """Update the map if it is valid.

        Update this map if it is the currently active map, and the
        vacuum is cleaning, or if it has never been set at all.
        """
        return self.cached_map == b"" or (
            self.is_selected
            and self.image_last_updated is not None
            and self.coordinator.roborock_device_info.props.status is not None
            and bool(self.coordinator.roborock_device_info.props.status.in_cleaning)
        )

    def _handle_coordinator_update(self) -> None:
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
            response = await asyncio.gather(
                *(
                    self.cloud_api.get_map_v1(),
                    self.coordinator.set_current_map_rooms(),
                ),
                return_exceptions=True,
            )
            if not isinstance(response[0], bytes):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="map_failure",
                )
            map_data = response[0]
            self.cached_map = self._create_image(map_data)
        return self.cached_map

    def _create_image(self, map_bytes: bytes) -> bytes:
        """Create an image using the map parser."""
        parsed_map = self.parser.parse(map_bytes)
        if parsed_map.image is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            )
        img_byte_arr = io.BytesIO()
        parsed_map.image.data.save(img_byte_arr, format="PNG")
        return img_byte_arr.getvalue()


async def create_coordinator_maps(
    coord: RoborockDataUpdateCoordinator, drawables: list[Drawable]
) -> list[RoborockMap]:
    """Get the starting map information for all maps for this device.

    The following steps must be done synchronously.
    Only one map can be loaded at a time per device.
    """
    entities = []
    cur_map = coord.current_map
    # This won't be None at this point as the coordinator will have run first.
    assert cur_map is not None
    # Sort the maps so that we start with the current map and we can skip the
    # load_multi_map call.
    maps_info = sorted(
        coord.maps.items(), key=lambda data: data[0] == cur_map, reverse=True
    )
    for map_flag, map_info in maps_info:
        # Load the map - so we can access it with get_map_v1
        if map_flag != cur_map:
            # Only change the map and sleep if we have multiple maps.
            await coord.api.send_command(RoborockCommand.LOAD_MULTI_MAP, [map_flag])
            coord.current_map = map_flag
            # We cannot get the map until the roborock servers fully process the
            # map change.
            await asyncio.sleep(MAP_SLEEP)
        # Get the map data
        map_update = await asyncio.gather(
            *[coord.cloud_api.get_map_v1(), coord.set_current_map_rooms()],
            return_exceptions=True,
        )
        # If we fail to get the map, we should set it to empty byte,
        # still create it, and set it as unavailable.
        api_data: bytes = map_update[0] if isinstance(map_update[0], bytes) else b""
        entities.append(
            RoborockMap(
                f"{slugify(coord.duid)}_map_{map_info.name}",
                coord,
                map_flag,
                api_data,
                map_info.name,
                drawables,
            )
        )
    if len(coord.maps) != 1:
        # Set the map back to the map the user previously had selected so that it
        # does not change the end user's app.
        # Only needs to happen when we changed maps above.
        await coord.cloud_api.send_command(RoborockCommand.LOAD_MULTI_MAP, [cur_map])
        coord.current_map = cur_map
    return entities
