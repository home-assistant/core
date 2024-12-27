"""Support for Tile device trackers."""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_utc

from . import TileCoordinator, TileData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_ALTITUDE = "altitude"
ATTR_CONNECTION_STATE = "connection_state"
ATTR_IS_DEAD = "is_dead"
ATTR_IS_LOST = "is_lost"
ATTR_LAST_LOST_TIMESTAMP = "last_lost_timestamp"
ATTR_LAST_TIMESTAMP = "last_timestamp"
ATTR_RING_STATE = "ring_state"
ATTR_TILE_NAME = "tile_name"
ATTR_VOIP_STATE = "voip_state"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tile device trackers."""
    data: TileData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            TileDeviceTracker(entry, data.coordinators[tile_uuid])
            for tile_uuid, tile in data.tiles.items()
        ]
    )


class TileDeviceTracker(CoordinatorEntity[TileCoordinator], TrackerEntity):
    """Representation of a network infrastructure device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "tile"

    def __init__(self, entry: ConfigEntry, coordinator: TileCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._tile = coordinator.tile
        self._attr_unique_id = f"{entry.data[CONF_USERNAME]}_{self._tile.uuid}"
        self._entry = entry

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and not self._tile.dead

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(identifiers={(DOMAIN, self._tile.uuid)}, name=self._tile.name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self._update_from_latest_data()
        self.async_write_ha_state()

    @callback
    def _update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        self._attr_longitude = (
            None if not self._tile.longitude else self._tile.longitude
        )
        self._attr_latitude = None if not self._tile.latitude else self._tile.latitude
        self._attr_location_accuracy = (
            0 if not self._tile.accuracy else int(self._tile.accuracy)
        )

        self._attr_extra_state_attributes = {
            ATTR_ALTITUDE: self._tile.altitude,
            ATTR_IS_LOST: self._tile.lost,
            ATTR_RING_STATE: self._tile.ring_state,
            ATTR_VOIP_STATE: self._tile.voip_state,
        }
        for timestamp_attr in (
            (ATTR_LAST_LOST_TIMESTAMP, self._tile.lost_timestamp),
            (ATTR_LAST_TIMESTAMP, self._tile.last_timestamp),
        ):
            if not timestamp_attr[1]:
                # If the API doesn't return a value for a particular timestamp
                # attribute, skip it:
                continue
            self._attr_extra_state_attributes[timestamp_attr[0]] = as_utc(
                timestamp_attr[1]
            )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._update_from_latest_data()
