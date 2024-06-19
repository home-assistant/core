"""Tankerkoenig sensor integration."""

from __future__ import annotations

import logging

from aiotankerkoenig import GasType, Station

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BRAND,
    ATTR_CITY,
    ATTR_FUEL_TYPE,
    ATTR_HOUSE_NUMBER,
    ATTR_POSTCODE,
    ATTR_STATION_NAME,
    ATTR_STREET,
    ATTRIBUTION,
)
from .coordinator import TankerkoenigConfigEntry, TankerkoenigDataUpdateCoordinator
from .entity import TankerkoenigCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankerkoenigConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the tankerkoenig sensors."""
    coordinator = entry.runtime_data

    entities = []
    for station in coordinator.stations.values():
        for fuel in (GasType.E10, GasType.E5, GasType.DIESEL):
            if getattr(station, fuel) is None:
                _LOGGER.debug(
                    "Station %s %s (%s) does not offer %s fuel, skipping",
                    station.brand,
                    station.name,
                    station.id,
                    fuel,
                )
                continue

            entities.append(
                FuelPriceSensor(
                    fuel,
                    station,
                    coordinator,
                )
            )

    async_add_entities(entities)


class FuelPriceSensor(TankerkoenigCoordinatorEntity, SensorEntity):
    """Contains prices for fuel in a given station."""

    _attr_attribution = ATTRIBUTION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _unrecorded_attributes = frozenset(
        {
            ATTR_BRAND,
            ATTR_CITY,
            ATTR_HOUSE_NUMBER,
            ATTR_POSTCODE,
            ATTR_STATION_NAME,
            ATTR_STREET,
            ATTRIBUTION,
            ATTR_LATITUDE,
            ATTR_LONGITUDE,
        }
    )

    def __init__(
        self,
        fuel_type: GasType,
        station: Station,
        coordinator: TankerkoenigDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, station)
        self._station_id = station.id
        self._fuel_type = fuel_type
        self._attr_translation_key = fuel_type
        self._attr_unique_id = f"{station.id}_{fuel_type}"
        attrs: dict[str, int | str | float | None] = {
            ATTR_BRAND: station.brand,
            ATTR_FUEL_TYPE: fuel_type,
            ATTR_STATION_NAME: station.name,
            ATTR_STREET: station.street,
            ATTR_HOUSE_NUMBER: station.house_number,
            ATTR_POSTCODE: station.post_code,
            ATTR_CITY: station.place,
        }

        if coordinator.show_on_map:
            attrs[ATTR_LATITUDE] = station.lat
            attrs[ATTR_LONGITUDE] = station.lng
        self._attr_extra_state_attributes = attrs

    @property
    def native_value(self) -> float:
        """Return the current price for the fuel type."""
        info = self.coordinator.data[self._station_id]
        return getattr(info, self._fuel_type)
