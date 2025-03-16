"""Support for Roborock image."""

import asyncio
from datetime import datetime
import logging

from roborock import RoborockCommand

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, IMAGE_CACHE_INTERVAL, MAP_SLEEP
from .coordinator import RoborockConfigEntry, RoborockDataUpdateCoordinator
from .entity import RoborockCoordinatedEntityV1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock image platform."""

    await asyncio.gather(
        *(refresh_coordinators(hass, coord) for coord in config_entry.runtime_data.v1)
    )
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
        content = await self.coordinator.map_storage.async_load_map(self.map_flag)
        self.cached_map = content or b""
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        # Bump last updated every third time the coordinator runs, so that async_image
        # will be called and we will evaluate on the new coordinator data if we should
        # update the cache.
        if self.is_selected and (
            (
                (dt_util.utcnow() - self.image_last_updated).total_seconds()
                > IMAGE_CACHE_INTERVAL
                and self.coordinator.roborock_device_info.props.status is not None
                and bool(self.coordinator.roborock_device_info.props.status.in_cleaning)
            )
            or self.cached_map == b""
        ):
            # This will tell async_image it should update.
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Update the image if it is not cached."""
        if self.is_selected:
            response = await asyncio.gather(
                *(
                    self.cloud_api.get_map_v1(),
                    self.coordinator.set_current_map_rooms(),
                ),
                return_exceptions=True,
            )
            if (
                not isinstance(response[0], bytes)
                or (content := self.coordinator.parse_image(response[0])) is None
            ):
                _LOGGER.debug("Failed to parse map contents: %s", response[0])
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="map_failure",
                )
            if self.cached_map != content:
                self.cached_map = content
                await self.coordinator.map_storage.async_save_map(
                    self.map_flag,
                    content,
                )
        return self.cached_map


async def refresh_coordinators(
    hass: HomeAssistant, coord: RoborockDataUpdateCoordinator
) -> None:
    """Get the starting map information for all maps for this device.

    The following steps must be done synchronously.
    Only one map can be loaded at a time per device.
    """
    cur_map = coord.current_map
    # This won't be None at this point as the coordinator will have run first.
    assert cur_map is not None
    map_flags = sorted(coord.maps, key=lambda data: data == cur_map, reverse=True)
    for map_flag in map_flags:
        if map_flag != cur_map:
            # Only change the map and sleep if we have multiple maps.
            await coord.api.send_command(RoborockCommand.LOAD_MULTI_MAP, [map_flag])
            coord.current_map = map_flag
            # We cannot get the map until the roborock servers fully process the
            # map change.
            await asyncio.sleep(MAP_SLEEP)
        await coord.set_current_map_rooms()

    if len(coord.maps) != 1:
        # Set the map back to the map the user previously had selected so that it
        # does not change the end user's app.
        # Only needs to happen when we changed maps above.
        await coord.cloud_api.send_command(RoborockCommand.LOAD_MULTI_MAP, [cur_map])
        coord.current_map = cur_map
