"""Tankerkoenig binary sensor integration."""

import logging
from typing import override

from aiotankerkoenig import PriceInfo, Station, Status

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityStateAttribute
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import JsonObjectType, JsonValueType

from .const import ATTR_OPENING_TIMES
from .coordinator import TankerkoenigConfigEntry, TankerkoenigDataUpdateCoordinator
from .entity import TankerkoenigCoordinatorEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# Tankerkoenig marks a station that never closes with `wholeDay` and sends no opening
# times for it. Returning that as an opening time keeps a single list for both.
WHOLE_DAY_OPENING_TIME: JsonObjectType = {
    "days": "Mo-So",
    "start_time": "00:00:00",
    "end_time": "23:59:59",
}


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

    _attr_device_class = BinarySensorDeviceClass.OPENING
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
        self._opening_times: list[JsonValueType] = []
        if station.whole_day:
            self._opening_times = [dict(WHOLE_DAY_OPENING_TIME)]
        elif station.opening_times:
            self._opening_times = [
                {
                    "days": opening_time.text,
                    "start_time": opening_time.start,
                    "end_time": opening_time.end,
                }
                for opening_time in station.opening_times
            ]
        if coordinator.show_on_map:
            self._attr_extra_state_attributes = {
                EntityStateAttribute.LATITUDE: station.lat,
                EntityStateAttribute.LONGITUDE: station.lng,
            }

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the station is open."""
        data: PriceInfo = self.coordinator.data[self._station_id]
        return data is not None and data.status == Status.OPEN

    async def async_get_opening_times(self) -> ServiceResponse:
        """Return the opening times of the station."""
        return {ATTR_OPENING_TIMES: self._opening_times}
