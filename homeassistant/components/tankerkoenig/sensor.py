"""Platform for tankerkoenig sensor integration."""
import logging

from datetime import timedelta
import pytankerkoenig

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
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
        vol.Optional(CONF_SCAN_INTERVAL, SCAN_INTERVAL): cv.time_period,
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

        for station in data["stations"]:
            if len(data["stations"]) <= 0:
                _LOGGER.error("Could not find any station in range")
            else:
                entities.append(
                    FuelPriceSensor(
                        api_key, fuel, station, f"{NAME}_{station['name']}_{fuel}"
                    )
                )

    async_add_entities(entities, True)


class FuelPriceSensor(Entity):
    """Contains prices for fuels in the given station."""

    def __init__(self, api_key, fuel_type, station, name=NAME):
        """Initialize the sensor."""
        self._api_key = api_key
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

    async def async_update(self):
        """Fetch new prices."""
        self._station = pytankerkoenig.getNearbyStations(
            self._api_key, self._latitude, self._longitude, 1, self._fuel_type, "dist"
        )["stations"][0]
        if self._station["isOpen"]:
            self._is_open = STATE_OPEN
        else:
            self._is_open = STATE_CLOSED
