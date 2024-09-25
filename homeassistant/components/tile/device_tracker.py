"""Support for Tile device trackers."""

from __future__ import annotations

import logging

from pytile.tile import Tile

from homeassistant.components.device_tracker import AsyncSeeCallback, TrackerEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.dt import as_utc

from . import TileData
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
            TileDeviceTracker(entry, data.coordinators[tile_uuid], tile)
            for tile_uuid, tile in data.tiles.items()
        ]
    )


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Detect a legacy configuration and import it."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )
    )

    _LOGGER.debug(
        "Your Tile configuration has been imported into the UI; "
        "please remove it from configuration.yaml"
    )

    return True


class TileDeviceTracker(CoordinatorEntity[DataUpdateCoordinator[None]], TrackerEntity):
    """Representation of a network infrastructure device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "tile"

    def __init__(
        self, entry: ConfigEntry, coordinator: DataUpdateCoordinator[None], tile: Tile
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{entry.data[CONF_USERNAME]}_{tile.uuid}"
        self._entry = entry
        self._tile = tile

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and not self._tile.dead

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device.

        Value in meters.
        """
        if not self._tile.accuracy:
            return super().location_accuracy
        return int(self._tile.accuracy)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(identifiers={(DOMAIN, self._tile.uuid)}, name=self._tile.name)

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if not self._tile.latitude:
            return None
        return self._tile.latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if not self._tile.longitude:
            return None
        return self._tile.longitude

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self._update_from_latest_data()
        self.async_write_ha_state()

    @callback
    def _update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
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
