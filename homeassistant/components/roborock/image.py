"""Support for Roborock image."""
import asyncio
import io
from itertools import chain

from roborock import MultiMapsList, RoborockCommand
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Sizes
from vacuum_map_parser_roborock.map_data_parser import RoborockMapDataParser

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import DOMAIN
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
        drawables: list[Drawable] = [
            Drawable.PATH,
            Drawable.CHARGER,
            Drawable.ROOM_NAMES,
        ]
        self.parser = RoborockMapDataParser(
            ColorsPalette(), Sizes(), drawables, ImageConfig(), []
        )
        self.async_update_token()
        self._attr_image_last_updated = dt_util.utcnow()
        self.map_flag = map_flag
        self.cached_map = self._create_image(starting_map)

    def should_update(self) -> bool:
        """Update this map if it is the current active map, it's been long enough, and the vacuum is cleaning."""
        return (
            self.map_flag == self.coordinator.current_map
            and self.image_last_updated is not None
            and (dt_util.utcnow() - self.image_last_updated).total_seconds() > 90
            and self.coordinator.roborock_device_info.props.status is not None
            and self.coordinator.roborock_device_info.props.status.in_cleaning
        )

    async def async_image(self) -> bytes | None:
        """Update the image if it is not cached."""
        if self.should_update():
            map_data: bytes = await self.cloud_api.get_map_v1()
            self.cached_map = self._create_image(map_data)
            self._attr_image_last_updated = dt_util.utcnow()
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
    """Get the starting map information for all maps for this device. The following steps must be done synchronously."""
    entities = []
    maps: MultiMapsList = await coord.cloud_api.get_multi_maps_list()
    cur_map = coord.current_map
    for roborock_map in maps.map_info:
        await coord.api.send_command(
            RoborockCommand.LOAD_MULTI_MAP, [roborock_map.mapFlag]
        )
        await asyncio.sleep(
            3
        )  # We cannot get the map until the roborock servers fully process the map change.
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
    await coord.cloud_api.send_command(RoborockCommand.LOAD_MULTI_MAP, [cur_map])
    return entities
