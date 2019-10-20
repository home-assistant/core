"""Base classe for tankerkoenig sensor integration."""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_CLOSED,
    STATE_OPEN,
)
from .const import NAME

_LOGGER = logging.getLogger(__name__)

ATTR_ADDRESS = "address"
ATTR_BRAND = "brand"
ATTR_FUEL = "fuel_type"
ATTR_IS_OPEN = "state"
ATTR_STATION_NAME = "station_name"
ATTRIBUTION = "Data provided by https://creativecommons.tankerkoenig.de"

ICON = "mdi:fuel"


class FuelPriceSensorBase(Entity):
    """Contains prices for fuels in the given station."""

    def __init__(self, fuel_type, station, name=NAME):
        """Initialize the sensor."""
        self._station = station
        self._fuel_type = fuel_type
        self._name = name
        self._latitude = station["lat"]
        self._longitude = station["lng"]
        if station["isOpen"]:
            self._is_open = STATE_OPEN
        else:
            self._is_open = STATE_CLOSED
        self._address = f"{station['street']} {station['houseNumber']}, {station['postCode']} {station['place']}"
        _LOGGER.debug(f"Setup standalone sensor {name}")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return "€"

    @property
    def state(self):
        """Return the state of the device."""
        return self._station["price"]

    @property
    def device_state_attributes(self):
        """Return the attributes of the device."""
        attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_BRAND: self._station["brand"],
            ATTR_FUEL: self._fuel_type,
            ATTR_STATION_NAME: self._station["name"],
            ATTR_ADDRESS: self._address,
            ATTR_LATITUDE: self._latitude,
            ATTR_LONGITUDE: self._longitude,
            ATTR_IS_OPEN: self._is_open,
        }
        return attrs

    @property
    def should_poll(self):
        """Do not poll regularly for the base class."""
        return False
