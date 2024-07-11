"""Sensor platform to display the current fuel prices at a NSW fuel station."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CURRENCY_CENT, UnitOfVolume
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DATA_NSW_FUEL_STATION, StationPriceData

_LOGGER = logging.getLogger(__name__)

ATTR_STATION_ID = "station_id"
ATTR_STATION_NAME = "station_name"

CONF_STATION_ID = "station_id"
CONF_FUEL_TYPES = "fuel_types"
CONF_ALLOWED_FUEL_TYPES = [
    "E10",
    "U91",
    "E85",
    "P95",
    "P98",
    "DL",
    "PDL",
    "B20",
    "LPG",
    "CNG",
    "EV",
]
CONF_DEFAULT_FUEL_TYPES = ["E10", "U91"]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STATION_ID): cv.positive_int,
        vol.Optional(CONF_FUEL_TYPES, default=CONF_DEFAULT_FUEL_TYPES): vol.All(
            cv.ensure_list, [vol.In(CONF_ALLOWED_FUEL_TYPES)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NSW Fuel Station sensor."""

    station_id = config[CONF_STATION_ID]
    fuel_types = config[CONF_FUEL_TYPES]

    coordinator = hass.data[DATA_NSW_FUEL_STATION]

    if coordinator.data is None:
        _LOGGER.error("Initial fuel station price data not available")
        return

    entities = []
    for fuel_type in fuel_types:
        if coordinator.data.prices.get((station_id, fuel_type)) is None:
            _LOGGER.error(
                "Fuel station price data not available for station %d and fuel type %s",
                station_id,
                fuel_type,
            )
            continue

        entities.append(StationPriceSensor(coordinator, station_id, fuel_type))

    add_entities(entities)


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
            ATTR_STATION_ID: self._station_id,
            ATTR_STATION_NAME: self._get_station_name(),
        }

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the units of measurement."""
        return f"{CURRENCY_CENT}/{UnitOfVolume.LITERS}"

    def _get_station_name(self):
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
