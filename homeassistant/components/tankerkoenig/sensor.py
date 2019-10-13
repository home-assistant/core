"""Platform for tankerkoenig sensor integration."""
import logging


import voluptuous as vol


import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    STATE_CLOSED,
    STATE_OPEN,
)
from .const import NAME

import pytankerkoenig

_LOGGER = logging.getLogger(__name__)

ATTR_FUEL = "Fuel_type"
ATTR_IS_OPEN = "Open"
ATTRIBUTION = "Data provided by https://creativecommons.tankerkoenig.de"

CONF_TYPES = "fuel_types"

ICON = "mdi:fuel"

FUEL_TYPES = ["e5", "e10", "diesel"]
DEFAULT_RADIUS = 5
# SCAN_INTERVAL = timedelta(minutes=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, NAME): cv.string,
        vol.Optional(CONF_TYPES, None): vol.All(cv.ensure_list, [vol.In(FUEL_TYPES)]),
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
    name = config.get(CONF_NAME)
    fuel_types = config.get(CONF_TYPES, FUEL_TYPES)
    api_key = config.get(CONF_API_KEY)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LATITUDE, hass.config.longitude)
    radius = config.get(CONF_RADIUS)
    #    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)

    data = pytankerkoenig.getNearbyStations(
        api_key, latitude, longitude, radius, fuel_types, "dist"
    )

    async_add_entities([FuelPriceSensor()], True)


class FuelPriceSensor(Entity):
    """Contains prices for fuels in the given station."""

    def __init__(self):
        """Initialize the sensor."""
        self._data = 1.239
        self._fuel_type = "e5"

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
            ATTR_FUEL: self._fuel_type,
            ATTR_IS_OPEN: STATE_CLOSED,
        }
        return attrs

    async def async_update(self):
        """Fetch new prices."""
        self._data = 1.429
