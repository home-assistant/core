"""Tankerkoenig binary sensor integration."""

import logging
from typing import Any

from aiotankerkoenig import PriceInfo, Station, Status

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TankerkoenigConfigEntry, TankerkoenigDataUpdateCoordinator
from .entity import TankerkoenigCoordinatorEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankerkoenigConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the tankerkoenig binary sensors."""
    coordinator = entry.runtime_data

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
        attrs: dict[str, Any] = {}
        if station.opening_times:
            attrs["opening_times"] = [
                {
                    "start": opening_time.start,
                    "end": opening_time.end,
                    "text": opening_time.text,
                }
                for opening_time in station.opening_times
            ]
        if station.whole_day is not None:
            attrs["whole_day"] = station.whole_day

        if coordinator.show_on_map:
            attrs[ATTR_LATITUDE] = station.lat
            attrs[ATTR_LONGITUDE] = station.lng

        if attrs:
            self._attr_extra_state_attributes = attrs

    @property
    def is_on(self) -> bool | None:
        """Return true if the station is open."""
        data: PriceInfo = self.coordinator.data[self._station_id]
        return data is not None and data.status == Status.OPEN
