"""Support for Australian BOM (Bureau of Meteorology) weather service."""
import logging

import voluptuous as vol

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS
from homeassistant.helpers import config_validation as cv

# Reuse data and API logic from the sensor implementation
from .sensor import CONF_STATION, BOMCurrentData, closest_station, validate_station

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME): cv.string, vol.Optional(CONF_STATION): validate_station}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the BOM weather platform."""
    station = config.get(CONF_STATION) or closest_station(
        config.get(CONF_LATITUDE), config.get(CONF_LONGITUDE), hass.config.config_dir
    )
    if station is None:
        _LOGGER.error("Could not get BOM weather station from lat/lon")
        return False
    bom_data = BOMCurrentData(station)
    try:
        bom_data.update()
    except ValueError as err:
        _LOGGER.error("Received error from BOM_Current: %s", err)
        return False
    add_entities([BOMWeather(bom_data, config.get(CONF_NAME))], True)


class BOMWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, bom_data, stationname=None):
        """Initialise the platform with a data instance and station name."""
        self.bom_data = bom_data
        self.stationname = stationname or self.bom_data.latest_data.get("name")

    def update(self):
        """Update current conditions."""
        self.bom_data.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"BOM {self.stationname or '(unknown station)'}"

    @property
    def condition(self):
        """Return the current condition."""
        return self.bom_data.get_reading("weather")

    # Now implement the WeatherEntity interface

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self.bom_data.get_reading("air_temp")

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the mean sea-level pressure."""
        return self.bom_data.get_reading("press_msl")

    @property
    def humidity(self):
        """Return the relative humidity."""
        return self.bom_data.get_reading("rel_hum")

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self.bom_data.get_reading("wind_spd_kmh")

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        directions = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
        wind = {name: idx * 360 / 16 for idx, name in enumerate(directions)}
        return wind.get(self.bom_data.get_reading("wind_dir"))

    @property
    def attribution(self):
        """Return the attribution."""
        return "Data provided by the Australian Bureau of Meteorology"
