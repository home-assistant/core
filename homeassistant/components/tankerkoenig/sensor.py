"""Platform for tankerkoenig sensor integration."""
import logging

import pytankerkoenig

import voluptuous as vol

from datetime import timedelta

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LOCATION,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    STATE_CLOSED,
    STATE_OPEN,
)
from .const import NAME

_LOGGER = logging.getLogger(__name__)

ATTR_BRAND = "brand"
ATTR_FUEL = "fuel_type"
ATTR_IS_OPEN = "state"
ATTR_STATION_NAME = "station_name"
ATTRIBUTION = "Data provided by https://creativecommons.tankerkoenig.de"

CONF_TYPES = "fuel_types"

ICON = "mdi:fuel"

FUEL_TYPES = ["e5", "e10", "diesel"]
DEFAULT_RADIUS = 5
SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_TYPES, ["e5", "e10", "diesel"]): vol.All(
            cv.ensure_list, [vol.In(FUEL_TYPES)]
        ),
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Optional(CONF_RADIUS, DEFAULT_RADIUS): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set the Tankerkoenig sensor platform up."""
    fuel_types = config.get(CONF_TYPES, FUEL_TYPES)
    api_key = config.get(CONF_API_KEY)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    radius = config.get(CONF_RADIUS, DEFAULT_RADIUS)

    entities = []
    for fuel in fuel_types:
        _LOGGER.debug(
            "Fetching data for (%s,%s) rad: %s fuel type: %s",
            latitude,
            longitude,
            radius,
            fuel,
        )
        data = pytankerkoenig.getNearbyStations(
            api_key, latitude, longitude, radius, fuel, "dist"
        )

        if len(data["stations"]) <= 0:
            _LOGGER.error("Could not find any station in range")
        else:
            station = data["stations"][0]
            entities.append(FuelPriceSensor(fuel, station))

    async_add_entities(entities, True)


class FuelPriceSensor(Entity):
    """Contains prices for fuels in the given station."""

    def __init__(self, fuel_type, station):
        """Initialize the sensor."""
        self._data = station["price"]
        self._fuel_type = fuel_type
        self._name = NAME
        self._station_name = station["name"]
        self._station_id = station["id"]
        if station["isOpen"]:
            self._is_open = STATE_OPEN
        else:
            self._is_open = STATE_CLOSED
        self._address = f"{station['street']} {station['houseNumber']}, {station['postCode']} {station['place']}"
        self._brand = station["brand"]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Tankerkoenig"

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
        return self._data

    @property
    def device_state_attributes(self):
        """Return the attributes of the device."""
        attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_BRAND: self._brand,
            ATTR_FUEL: self._fuel_type,
            ATTR_STATION_NAME: self._station_name,
            ATTR_LOCATION: self._address,
            ATTR_IS_OPEN: self._is_open,
        }
        return attrs

    async def async_update(self):
        """Fetch new prices."""
        self._data = 1.429
