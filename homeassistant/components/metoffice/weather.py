"""Support for UK Met Office weather service."""
import logging

import datapoint as dp
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    PLATFORM_SCHEMA,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv

from .sensor import ATTRIBUTION, CONDITION_CLASSES, MetOfficeData

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Met Office"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Met Office weather platform."""
    name = config.get(CONF_NAME)
    datapoint = dp.connection(api_key=config.get(CONF_API_KEY))

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    try:
        site = datapoint.get_nearest_forecast_site(
            latitude=latitude, longitude=longitude
        )
    except dp.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return

    if not site:
        _LOGGER.error("Unable to get nearest Met Office forecast site")
        return

    data = MetOfficeData(hass, datapoint, site)
    try:
        data.update(forecast=True)
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
        self.data.update(forecast=True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self.site.name}"

    @property
    def condition(self):
        """Return the current condition."""
        return [
            k
            for k, v in CONDITION_CLASSES.items()
            if self.data.current.weather.value in v
        ][0]

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self.data.current.temperature.value

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
        return self.data.current.humidity.value

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self.data.current.wind_speed.value

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.data.current.wind_direction.value

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        data = [
            {
                ATTR_FORECAST_TIME: day.timesteps[1].date,
                ATTR_FORECAST_TEMP: day.timesteps[1].temperature.value,
                ATTR_FORECAST_TEMP_LOW: day.timesteps[0].temperature.value,
                ATTR_FORECAST_WIND_SPEED: day.timesteps[1].wind_speed.value,
                ATTR_FORECAST_WIND_BEARING: day.timesteps[1].wind_direction.value,
                ATTR_FORECAST_CONDITION: [
                    k
                    for k, v in CONDITION_CLASSES.items()
                    if day.timesteps[1].weather.value in v
                ][0],
            }
            for day in self.data.forecast
        ]

        return data
