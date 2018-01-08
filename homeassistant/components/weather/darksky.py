"""
Patform for retrieving meteorological data from Dark Sky.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/weather.darksky/
"""
from datetime import datetime, timedelta
import logging

from requests.exceptions import (
    ConnectionError as ConnectError, HTTPError, Timeout)
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_TEMP, ATTR_FORECAST_TIME, PLATFORM_SCHEMA, WeatherEntity)
from homeassistant.const import (
    CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS,
    TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['python-forecastio==1.3.5']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Powered by Dark Sky"

ATTR_DAILY_FORECAST_SUMMARY = 'daily_forecast_summary'
ATTR_HOURLY_FORECAST_SUMMARY = 'hourly_forecast_summary'

CONF_UNITS = 'units'

DEFAULT_NAME = 'Dark Sky'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_UNITS): vol.In(['auto', 'si', 'us', 'ca', 'uk', 'uk2']),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=3)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Dark Sky weather."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)

    units = config.get(CONF_UNITS)
    if not units:
        units = 'si' if hass.config.units.is_metric else 'us'

    dark_sky = DarkSkyData(
        config.get(CONF_API_KEY), latitude, longitude, units)

    add_devices([DarkSkyWeather(name, dark_sky)], True)


class DarkSkyWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, name, dark_sky):
        """Initialize Dark Sky weather."""
        self._name = name
        self._dark_sky = dark_sky

        self._ds_data = None
        self._ds_currently = None
        self._ds_hourly = None
        self._ds_daily = None

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def temperature(self):
        """Return the temperature."""
        return self._ds_currently.get('temperature')

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT if 'us' in self._dark_sky.units \
            else TEMP_CELSIUS

    @property
    def humidity(self):
        """Return the humidity."""
        return self._ds_currently.get('humidity') * 100.0

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._ds_currently.get('windSpeed')

    @property
    def pressure(self):
        """Return the pressure."""
        return self._ds_currently.get('pressure')

    @property
    def condition(self):
        """Return the weather condition."""
        return self._ds_currently.get('summary')

    @property
    def forecast(self):
        """Return the forecast array."""
        return [{
            ATTR_FORECAST_TIME:
                datetime.fromtimestamp(entry.d.get('time')).isoformat(),
            ATTR_FORECAST_TEMP: entry.d.get('temperature')}
                for entry in self._ds_hourly.data]

    @property
    def hourly_forecast_summary(self):
        """Return a summary of the hourly forecast."""
        return self._ds_hourly.summary

    @property
    def daily_forecast_summary(self):
        """Return a summary of the daily forecast."""
        return self._ds_daily.summary

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            ATTR_DAILY_FORECAST_SUMMARY: self.daily_forecast_summary,
            ATTR_HOURLY_FORECAST_SUMMARY: self.hourly_forecast_summary
        }
        return attrs

    def update(self):
        """Get the latest data from Dark Sky."""
        self._dark_sky.update()

        self._ds_data = self._dark_sky.data
        self._ds_currently = self._dark_sky.currently.d
        self._ds_hourly = self._dark_sky.hourly
        self._ds_daily = self._dark_sky.daily


class DarkSkyData(object):
    """Get the latest data from Dark Sky."""

    def __init__(self, api_key, latitude, longitude, units):
        """Initialize the data object."""
        self._api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.requested_units = units

        self.data = None
        self.currently = None
        self.hourly = None
        self.daily = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Dark Sky."""
        import forecastio

        try:
            self.data = forecastio.load_forecast(
                self._api_key, self.latitude, self.longitude,
                units=self.requested_units)
            self.currently = self.data.currently()
            self.hourly = self.data.hourly()
            self.daily = self.data.daily()
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            _LOGGER.error("Unable to connect to Dark Sky. %s", error)
            self.data = None

    @property
    def units(self):
        """Get the unit system of returned data."""
        return self.data.json.get('flags').get('units')
