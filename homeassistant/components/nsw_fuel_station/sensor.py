"""Sensor platform to display the current fuel prices at a NSW fuel station."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_CENT, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DATA_NSW_FUEL_STATION, StationPriceData
from .const import (
    ATTR_FUEL_TYPE,
    ATTR_STATION_ADDRESS,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    CONF_FUEL_TYPES,
    CONF_STATION_ID,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    sensors = []
    station_id = entry.data[CONF_STATION_ID]
    fuel_types = entry.data[CONF_FUEL_TYPES]

    coordinator = hass.data[DATA_NSW_FUEL_STATION]

    if coordinator.data is None:
        _LOGGER.error("Initial fuel station price data not available")
        return

    for fuel_type in fuel_types:
        if coordinator.data.prices.get((station_id, fuel_type)) is None:
            _LOGGER.error(
                "Fuel station price data not available for station %d and fuel type %s",
                station_id,
                fuel_type,
            )
            continue

        sensors.append(StationPriceSensor(coordinator, station_id, fuel_type))
    async_add_entities(sensors)


class StationPriceSensor(
    CoordinatorEntity[DataUpdateCoordinator[StationPriceData]], SensorEntity
):
    """Implementation of a sensor that reports the fuel price for a station."""

    _attr_attribution = "Data provided by NSW Government FuelCheck"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[StationPriceData],
        station_id: int,
        fuel_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._station_id = station_id
        self._fuel_type = fuel_type

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        station_name = self._get_station_name()
        return f"{station_name} {self._fuel_type}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        prices = self.coordinator.data.prices
        return prices.get((self._station_id, self._fuel_type))

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        """Return the state attributes of the device."""
        return {
            ATTR_FUEL_TYPE: self._get_fuel_type(),
            ATTR_STATION_ADDRESS: self._get_station_address(),
            ATTR_STATION_ID: self._station_id,
            ATTR_STATION_NAME: self._get_station_name(),
        }

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the units of measurement."""
        return f"{CURRENCY_CENT}/{UnitOfVolume.LITERS}"

    def _get_fuel_type(self) -> str:
        if self.coordinator.data is None:
            return self._fuel_type
        return self.coordinator.data.fuel_types.get(self._fuel_type, self._fuel_type)

    def _get_station_address(self) -> str:
        default_address = "Unknown address"
        if self.coordinator.data is None:
            return default_address

        station = self.coordinator.data.stations.get(self._station_id)
        if station is None:
            return default_address

        return station.address

    def _get_station_name(self) -> str:
        default_name = f"station {self._station_id}"
        if self.coordinator.data is None:
            return default_name

        station = self.coordinator.data.stations.get(self._station_id)
        if station is None:
            return default_name

        return station.name

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self._station_id}_{self._fuel_type}"
