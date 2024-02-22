"""Tankerkoenig binary sensor integration."""
from __future__ import annotations

import logging

from aiotankerkoenig import PriceInfo, Station, Status

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TankerkoenigDataUpdateCoordinator
from .entity import TankerkoenigCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the tankerkoenig binary sensors."""
    coordinator: TankerkoenigDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StationOpenBinarySensorEntity(
            station,
            coordinator,
        )
        for station in coordinator.stations.values()
    )


class StationOpenBinarySensorEntity(TankerkoenigCoordinatorEntity, BinarySensorEntity):
    """Shows if a station is open or closed."""

    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_translation_key = "status"

    def __init__(
        self,
        station: Station,
        coordinator: TankerkoenigDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, station)
        self._station_id = station.id
        self._attr_unique_id = f"{station.id}_status"
        if coordinator.show_on_map:
            self._attr_extra_state_attributes = {
                ATTR_LATITUDE: station.lat,
                ATTR_LONGITUDE: station.lng,
            }

    @property
    def is_on(self) -> bool | None:
        """Return true if the station is open."""
        data: PriceInfo = self.coordinator.data[self._station_id]
        return data is not None and data.status == Status.OPEN
