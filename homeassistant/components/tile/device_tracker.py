"""Support for Tile device trackers."""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import as_utc

from .coordinator import TileConfigEntry, TileCoordinator
from .entity import TileEntity

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
    hass: HomeAssistant,
    entry: TileConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tile device trackers."""

    async_add_entities(
        TileDeviceTracker(coordinator) for coordinator in entry.runtime_data.values()
    )


class TileDeviceTracker(TileEntity, TrackerEntity):
    """Representation of a network infrastructure device."""

    _attr_name = None
    _attr_translation_key = "tile"

    def __init__(self, coordinator: TileCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{coordinator.username}_{self._tile.uuid}"

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
