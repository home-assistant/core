"""
Support for UK Met Office weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.metoffice/
"""
import logging

import voluptuous as vol

from homeassistant.components.weather import WeatherEntity, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, TEMP_CELSIUS, CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers import config_validation as cv
# Reuse data and API logic from the sensor implementation
from homeassistant.components.sensor.metoffice import \
    MetOfficeCurrentData, CONF_ATTRIBUTION, CONDITION_CLASSES

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['datapoint==0.4.3']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Met Office weather platform."""
    import datapoint as dp
    datapoint = dp.connection(api_key=config.get(CONF_API_KEY))

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    try:
        site = datapoint.get_nearest_site(latitude=latitude,
                                          longitude=longitude)
    except dp.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return False

    if not site:
        _LOGGER.error("Unable to get nearest Met Office forecast site")
        return False

    # Get data
    data = MetOfficeCurrentData(hass, datapoint, site)
    try:
        data.update()
    except (ValueError, dp.exceptions.APIException) as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return False
    add_devices([MetOfficeWeather(site, data, config.get(CONF_NAME))],
                True)
    return True


class MetOfficeWeather(WeatherEntity):
    """Implementation of a Met Office weather condition."""

    def __init__(self, site, data, config):
        """Initialise the platform with a data instance and site."""
        self.data = data
        self.site = site

    def update(self):
        """Update current conditions."""
        self.data.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Met Office ({})'.format(self.site.name)

    @property
    def condition(self):
        """Return the current condition."""
        return [k for k, v in CONDITION_CLASSES.items() if
                self.data.data.weather.value in v][0]

    # Now implement the WeatherEntity interface

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self.data.data.temperature.value

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the mean sea-level pressure."""
        return None

    @property
    def humidity(self):
        """Return the relative humidity."""
        return self.data.data.humidity.value

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self.data.data.wind_speed.value

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.data.data.wind_direction.value

    @property
    def attribution(self):
        """Return the attribution."""
        return CONF_ATTRIBUTION
