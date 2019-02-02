"""
Support for Yr.no weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.norway_air/
"""
import logging

from datetime import timedelta
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_LATITUDE, CONF_LONGITUDE,
                                 ATTR_ATTRIBUTION, CONF_NAME)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util


REQUIREMENTS = ['pyMetno==0.4.3']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Air quality from met.no, delivered " \
                   "by the Norwegian Meteorological Institute."
# https://api.met.no/license_data.html

CONF_FORECAST = 'forecast'

DEFAULT_FORECAST = 0
DEFAULT_NAME = 'Air quality'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FORECAST, default=DEFAULT_FORECAST): vol.Coerce(int),
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the air_quality norway sensor."""
    forecast = config.get(CONF_FORECAST)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    coordinates = {
        'lat': str(latitude),
        'lon': str(longitude),
    }

    async_add_entities([AirSensor(name, coordinates,
                                  forecast, async_get_clientsession(hass))],
                       True)


class AirSensor(Entity):
    """Representation of an Yr.no sensor."""

    def __init__(self, name, coordinates, forecast, session):
        """Initialize the sensor."""
        import metno
        self._name = name
        self._data = metno.AirQualityData(coordinates, forecast, session)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._data.state

    async def async_update(self):
        """Update the sensor."""
        await self._data.update()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            'Time': dt_util.as_local(self._data.time),
            'Level': self._data.level,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._data.unit_of_measurement
