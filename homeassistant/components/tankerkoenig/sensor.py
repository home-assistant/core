"""Tankerkoenig sensor integration."""

import logging

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNKNOWN,
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

ATTR_ADDRESS = "address"
ATTR_BRAND = "brand"
ATTR_FUEL_TYPE = "fuel_type"
ATTR_IS_OPEN = "is_open"
ATTR_STATION_NAME = "station_name"
ATTRIBUTION = "Data provided by https://creativecommons.tankerkoenig.de"

ICON = "mdi:fuel"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the tankerkoenig sensors."""
    tankerkoenig = hass.data[DOMAIN]
    _LOGGER.debug("Setup platform. Stations: %s ", tankerkoenig.entity_list)
    async_add_entities(tankerkoenig.entity_list)


class FuelPriceSensor(Entity):
    """Contains prices for fuel in a given station."""

    def __init__(self, fuel_type, station, name=NAME):
        """Initialize the sensor."""
        self._station = station
        self._station_id = station["id"]
        self._fuel_type = fuel_type
        self._name = name
        self._latitude = station["lat"]
        self._longitude = station["lng"]
        self._is_open = STATE_OPEN if station["isOpen"] else STATE_CLOSED
        self._address = f"{station['street']} {station['houseNumber']}, {station['postCode']} {station['place']}"
        _LOGGER.debug("Setup sensor %s", name)
        self._price = station[fuel_type]

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
        return self._price

    @property
    def device_state_attributes(self):
        """Return the attributes of the device."""
        attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_BRAND: self._station["brand"],
            ATTR_FUEL_TYPE: self._fuel_type,
            ATTR_STATION_NAME: self._station["name"],
            ATTR_ADDRESS: self._address,
            ATTR_LATITUDE: self._latitude,
            ATTR_LONGITUDE: self._longitude,
            ATTR_IS_OPEN: self._is_open,
        }
        return attrs

    def new_data(self, data):
        """Update the internal sensor data."""
        if data is None or "status" not in data.keys():
            _LOGGER.warning("Received no data for station %s", self._station_id)
            self._is_open = STATE_UNKNOWN
            self._price = None
        else:
            self._is_open = STATE_OPEN if data["status"] == "open" else STATE_CLOSED
            self._price = data.get(self._fuel_type)
        self.update()

    def update(self):
        """Update the data in the HASS backend."""
        pass
