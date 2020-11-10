"""Sensor platform to display the current fuel prices at a NSW fuel station."""
import logging
from typing import Optional

import voluptuous as vol
from nsw_fuel import FuelCheckError, FuelCheckClient

import homeassistant.helpers.config_validation as cv
from homeassistant.components.nsw_fuel_station import (
    DATA_NSW_FUEL_STATION,
    DATA_ATTR_CLIENT, DATA_ATTR_REFERENCE_DATA, SharedReferenceData,
    MIN_TIME_BETWEEN_UPDATES)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CURRENCY_CENT, VOLUME_LITERS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

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

ATTRIBUTION = "Data provided by NSW Government FuelCheck"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STATION_ID): cv.positive_int,
        vol.Optional(CONF_FUEL_TYPES, default=CONF_DEFAULT_FUEL_TYPES): vol.All(
            cv.ensure_list, [vol.In(CONF_ALLOWED_FUEL_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NSW Fuel Station sensor."""

    station_id = config[CONF_STATION_ID]
    fuel_types = config[CONF_FUEL_TYPES]

    client = hass.data[DATA_NSW_FUEL_STATION][DATA_ATTR_CLIENT]
    reference_data = hass.data[DATA_NSW_FUEL_STATION][DATA_ATTR_REFERENCE_DATA]

    station_data = StationPriceData(client, station_id)
    station_data.update()

    add_entities(
        [StationPriceSensor(station_id, reference_data, station_data,
                            fuel_type) for
         fuel_type in fuel_types])


class StationPriceData:
    """An object to store and fetch the latest data for a given station."""

    def __init__(self, client: FuelCheckClient, station_id: int) -> None:
        """Initialize the sensor."""
        self._station_id = station_id
        self._client = client
        self._data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the internal data using the API client."""
        try:
            self._data = self._client.get_fuel_prices_for_station(
                self._station_id)
        except FuelCheckError as exc:
            _LOGGER.error("Failed to fetch NSW Fuel station price data. %s", exc)

    def for_fuel_type(self, fuel_type: str):
        """Return the price of the given fuel type."""
        if self._data is None:
            return None
        return next(
            (price for price in self._data if price.fuel_type == fuel_type), None
        )

    def get_available_fuel_types(self):
        """Return the available fuel types for the station."""
        return [price.fuel_type for price in self._data]


class StationPriceSensor(Entity):
    """Implementation of a sensor that reports the fuel price for a station."""

    def __init__(self, station_id: int, reference_data: SharedReferenceData,
                 station_data: StationPriceData, fuel_type: str):
        """Initialize the sensor."""
        self._station_id = station_id
        self._reference_data = reference_data
        self._station_data = station_data
        self._fuel_type = fuel_type

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        station_name = self._reference_data.get_station_name(self._station_id)
        return f"{station_name} {self._fuel_type}"

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        price_info = self._station_data.for_fuel_type(self._fuel_type)
        if price_info:
            return price_info.price

        return None

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes of the device."""
        return {
            ATTR_STATION_ID: self._station_id,
            ATTR_STATION_NAME: self._reference_data.get_station_name(
                self._station_id),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    @property
    def unit_of_measurement(self) -> str:
        """Return the units of measurement."""
        return f"{CURRENCY_CENT}/{VOLUME_LITERS}"

    def update(self):
        """Update current conditions."""
        self._reference_data.update()
        self._station_data.update()
