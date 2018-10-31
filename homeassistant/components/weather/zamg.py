"""
Sensor for data from Austrian "Zentralanstalt für Meteorologie und Geodynamik".

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.zamg/
"""
import logging

import voluptuous as vol

from homeassistant.components.weather import (
    WeatherEntity, ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE, ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, TEMP_CELSIUS, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers import config_validation as cv
# Reuse data and API logic from the sensor implementation
from homeassistant.components.sensor.zamg import (
    ATTRIBUTION, closest_station, CONF_STATION_ID, zamg_stations, ZamgData)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_STATION_ID): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ZAMG weather platform."""
    name = config.get(CONF_NAME)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    station_id = config.get(CONF_STATION_ID) or closest_station(
        latitude, longitude, hass.config.config_dir)
    if station_id not in zamg_stations(hass.config.config_dir):
        _LOGGER.error("Configured ZAMG %s (%s) is not a known station",
                      CONF_STATION_ID, station_id)
        return False

    probe = ZamgData(station_id=station_id)
    try:
        probe.update()
    except (ValueError, TypeError) as err:
        _LOGGER.error("Received error from ZAMG: %s", err)
        return False

    add_entities([ZamgWeather(probe, name)], True)


class ZamgWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, zamg_data, stationname=None):
        """Initialise the platform with a data instance and station name."""
        self.zamg_data = zamg_data
        self.stationname = stationname

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.stationname or 'ZAMG {}'.format(
            self.zamg_data.data.get('Name') or '(unknown station)')

    @property
    def condition(self):
        """Return the current condition."""
        return None

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self.zamg_data.get_data(ATTR_WEATHER_TEMPERATURE)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return self.zamg_data.get_data(ATTR_WEATHER_PRESSURE)

    @property
    def humidity(self):
        """Return the humidity."""
        return self.zamg_data.get_data(ATTR_WEATHER_HUMIDITY)

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self.zamg_data.get_data(ATTR_WEATHER_WIND_SPEED)

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.zamg_data.get_data(ATTR_WEATHER_WIND_BEARING)

    def update(self):
        """Update current conditions."""
        self.zamg_data.update()
