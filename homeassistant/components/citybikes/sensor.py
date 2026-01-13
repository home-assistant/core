"""Sensor for the CityBikes data."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import location as location_util

from .const import (
    ATTR_EBIKE,
    ATTR_EMPTY_SLOTS,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_TIMESTAMP,
    ATTR_UID,
    CITYBIKES_ATTRIBUTION,
    CONF_ALL_STATIONS,
    CONF_NETWORK,
    CONF_RADIUS,
    CONF_STATIONS_LIST,
    DOMAIN,
)
from .coordinator import CityBikesCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="bikes",
        translation_key="bikes",
        native_unit_of_measurement="bikes",
        icon="mdi:bike",
    ),
    SensorEntityDescription(
        key="ebikes",
        translation_key="ebikes",
        native_unit_of_measurement="bikes",
        icon="mdi:lightning-bolt",
    ),
    SensorEntityDescription(
        key="empty_slots",
        translation_key="empty_slots",
        native_unit_of_measurement="slots",
        icon="mdi:parking",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CityBikes sensor entities from a config entry."""
    coordinator: CityBikesCoordinator = entry.runtime_data
    options = entry.options or {}
    all_stations = options.get(CONF_ALL_STATIONS, True)
    stations_list = set(options.get(CONF_STATIONS_LIST, []))
    radius = options.get(CONF_RADIUS, 0)
    
    # Use location from options if provided, otherwise use Home Assistant's configured location
    latitude = options.get(CONF_LATITUDE, hass.config.latitude)
    longitude = options.get(CONF_LONGITUDE, hass.config.longitude)

    entities: list[CityBikesStation] = []
    data = coordinator.data
    if data and "stations" in data:
        for station in data["stations"]:
            station_id = station.id
            station_uid = str(station.extra.get(ATTR_UID, ""))

            # If explicit station list is selected, only include those stations
            if not all_stations:
                if not stations_list.intersection((station_id, station_uid)):
                    continue
            # If "all stations" is selected, apply radius filter if set
            elif radius > 0:
                dist = location_util.distance(
                    latitude, longitude, station.latitude, station.longitude
                )
                if dist is None or dist > radius:
                    continue

            # Create multiple entities per station (bikes, ebikes, empty_slots)
            for description in SENSOR_TYPES:
                entities.append(
                    CityBikesStation(
                        coordinator,
                        entry,
                        station_id,
                        description,
                    )
                )

    async_add_entities(entities)


class CityBikesStation(CoordinatorEntity[CityBikesCoordinator], SensorEntity):
    """CityBikes API Sensor."""

    _attr_attribution = CITYBIKES_ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CityBikesCoordinator,
        entry: ConfigEntry,
        station_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._station_id = station_id
        self._entry = entry
        # Unique ID includes the sensor type to differentiate entities
        self._attr_unique_id = f"{entry.data[CONF_NETWORK]}_{station_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        station = self._get_station()
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data[CONF_NETWORK]}_{self._station_id}")},
            name=station.name if station else f"Station {self._station_id}",
            manufacturer="CityBikes",
            model="Bike Share Station",
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "stations" not in self.coordinator.data:
            return None
        
        station = self._get_station()
        if not station:
            return None
        
        key = self.entity_description.key
        if key == "bikes":
            return station.free_bikes
        if key == "ebikes":
            return station.extra.get(ATTR_EBIKE)
        if key == "empty_slots":
            return station.empty_slots
        
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        station = self._get_station()
        if not station:
            return {}
        
        attrs = {
            ATTR_UID: station.extra.get(ATTR_UID),
            ATTR_LATITUDE: station.latitude,
            ATTR_LONGITUDE: station.longitude,
            ATTR_TIMESTAMP: station.timestamp,
        }
        
        # Add complementary data based on sensor type
        key = self.entity_description.key
        if key == "bikes":
            attrs[ATTR_EMPTY_SLOTS] = station.empty_slots
            attrs[ATTR_EBIKE] = station.extra.get(ATTR_EBIKE)
        elif key == "ebikes":
            attrs[ATTR_EMPTY_SLOTS] = station.empty_slots
            # Calculate regular bikes (total - ebikes)
            ebikes = station.extra.get(ATTR_EBIKE)
            if ebikes is not None and station.free_bikes is not None:
                attrs["regular_bikes"] = station.free_bikes - ebikes
        elif key == "empty_slots":
            attrs[ATTR_EBIKE] = station.extra.get(ATTR_EBIKE)
        
        return attrs

    def _get_station(self):
        """Get the station data from coordinator."""
        if not self.coordinator.data or "stations" not in self.coordinator.data:
            return None
        
        for station in self.coordinator.data["stations"]:
            if station.id == self._station_id:
                return station
        return None

    def _get_station_name(self) -> str | None:
        """Get the station name."""
        station = self._get_station()
        if station:
            return station.name
        return None
