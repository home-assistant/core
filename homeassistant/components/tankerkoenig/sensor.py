"""Platform for tankerkoenig sensor integration."""
import logging

from datetime import timedelta
import pytankerkoenig

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    STATE_CLOSED,
    STATE_OPEN,
)
from .const import NAME, CONF_TYPES, FUEL_TYPES
from .base_sensor import FuelPriceSensorBase

_LOGGER = logging.getLogger(__name__)

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
    _LOGGER.debug("Fetching data for (%s,%s) rad: %s", latitude, longitude, radius)
    data = pytankerkoenig.getNearbyStations(
        api_key, latitude, longitude, radius, "all", "dist"
    )
    _LOGGER.debug("Received data: %s", data)
    if not data["ok"]:
        _LOGGER.error("Error fetching data from tankerkoenig.de:\n%s", data["message"])
        _LOGGER.error("Could not setup sensors")
        return

    master = None
    for station in data["stations"]:
        if len(data["stations"]) <= 0:
            _LOGGER.error("Could not find any station in range")
        else:
            for fuel in fuel_types:
                sensor = None
                if master is None:
                    master = FuelPriceSensorMaster(
                        api_key, fuel, station, f"{NAME}_{station['name']}_{fuel}"
                    )
                    sensor = master
                else:
                    sensor = FuelPriceSensorSlave(
                        fuel, station, f"{NAME}_{station['name']}_{fuel}"
                    )
                    master.add_slave(fuel, sensor)
                entities.append(sensor)

    async_add_entities(entities, True)


class FuelPriceSensorMaster(FuelPriceSensorBase):
    """Master sensor for tankerkoenig prices. This sensor gets the updated prices and forwards them to any slaves."""

    def __init__(self, api_key, fuel_type, station, name=NAME):
        """Initialize the class."""
        super().__init__(fuel_type, station, name)
        self._api_key = api_key
        self._slaves = {}

    @property
    def should_poll(self):
        """Poll regularly for the standalone sensor."""
        return True

    def add_slave(self, fuel_type, slave):
        """Add an additional slave sensor, that needs to be updated together with this one."""
        self._slaves[fuel_type] = slave

    async def async_update(self):
        """Fetch new prices."""
        _LOGGER.debug("Fetching new prices for standalone sensor")
        data = pytankerkoenig.getPriceList(self._api_key, [self._station_id])
        if data["ok"]:
            _LOGGER.debug("Received data: %s", data)
            self._data = data["prices"][self._station_id]
            if self._data["status"] == "open":
                self._is_open = STATE_OPEN
            else:
                self._is_open = STATE_CLOSED
            for fuel_type, slave in self._slaves.items():
                slave.new_data(self._data)
        else:
            _LOGGER.error(
                "Error fetching data from tankerkoenig.de: %s", data["message"]
            )


class FuelPriceSensorSlave(FuelPriceSensorBase):
    """Contains prices for fuels in the given station."""

    def new_data(self, data):
        """Update the internal sensor data."""
        self._data = data
        if self._data["status"] == "open":
            self._is_open = STATE_OPEN
        else:
            self._is_open = STATE_CLOSED
