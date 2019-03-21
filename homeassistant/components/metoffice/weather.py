"""Support for UK Met Office weather service."""
import logging

import voluptuous as vol

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.const import (
    CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS)
from homeassistant.helpers import config_validation as cv

from .sensor import ATTRIBUTION, CONDITION_CLASSES, MetOfficeCurrentData

REQUIREMENTS = ['datapoint==0.4.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Met Office"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Met Office weather platform."""
    import datapoint as dp

    name = config.get(CONF_NAME)
    datapoint = dp.connection(api_key=config.get(CONF_API_KEY))

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    try:
        site = datapoint.get_nearest_site(
            latitude=latitude, longitude=longitude)
    except dp.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return

    if not site:
        _LOGGER.error("Unable to get nearest Met Office forecast site")
        return

    data = MetOfficeCurrentData(hass, datapoint, site)
    try:
        data.update()
    except (ValueError, dp.exceptions.APIException) as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return

    add_entities([MetOfficeWeather(site, data, name)], True)


class MetOfficeWeather(WeatherEntity):
    """Implementation of a Met Office weather condition."""

    def __init__(self, site, data, name):
        """Initialise the platform with a data instance and site."""
        self._name = name
        self.data = data
        self.site = site

    def update(self):
        """Update current conditions."""
        self.data.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, self.site.name)

    @property
    def condition(self):
        """Return the current condition."""
        return [k for k, v in CONDITION_CLASSES.items() if
                self.data.data.weather.value in v][0]

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
        return ATTRIBUTION
