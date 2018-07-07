"""
Platform for retrieving meteorological data from Environment Canada.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/weather.environmentcanada/
"""
import logging
import datetime

import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION, ATTR_FORECAST_TEMP, ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME, PLATFORM_SCHEMA, WeatherEntity)
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS)
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

from homeassistant.components.sensor.environment_canada import (
    ECData, get_station, validate_station,
    CONF_STATION, CONF_ATTRIBUTION, MIN_TIME_BETWEEN_UPDATES)

_LOGGER = logging.getLogger(__name__)

CONF_UNITS = 'units'
CONF_FORECAST = 'forecast'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_STATION): validate_station,
    vol.Inclusive(CONF_LATITUDE, 'latlon'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'latlon'): cv.longitude,
    vol.Required(CONF_FORECAST, default='daily'):
        vol.In(['daily', 'hourly']),
})

# Icon codes from http://dd.weatheroffice.ec.gc.ca/citypage_weather/
# docs/current_conditions_icon_code_descriptions_e.csv
ICON_CONDITION_MAP = {'sunny': [0, 1],
                      'clear-night': [30, 31],
                      'partlycloudy': [2, 3, 4, 5, 22, 32, 33, 34, 35],
                      'cloudy': [10],
                      'rainy': [6, 9, 11, 12, 28, 36],
                      'lightning-rainy': [19, 39, 46, 47],
                      'pouring': [13],
                      'snowy-rainy': [7, 14, 15, 27, 37],
                      'snowy': [8, 16, 17, 18, 25, 26, 38, 40],
                      'windy': [43],
                      'fog': [20, 21, 23, 24, 44],
                      'hail': [26, 27]}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Environment Canada weather."""
    station = get_station(hass, config)
    ec_data = ECData(hass, station)

    try:
        ec_data.update()
    except ValueError as err:
        _LOGGER.error("Received error from EC Current: %s", err)
        return

    add_devices([ECWeather(ec_data, config)])


class ECWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, ec_data, config):
        """Initialize Environment Canada weather."""
        self.data_object = ec_data
        self.data_element = ec_data.data
        self._name = config.get(CONF_NAME)
        self.forecast_type = config.get(CONF_FORECAST, 'daily')

    @property
    def attribution(self):
        """Return the attribution."""
        return CONF_ATTRIBUTION

    @property
    def name(self):
        """Return the name of the weather entity."""
        if self._name:
            return self._name
        return self.data_element.findtext('./location/name')

    @property
    def temperature(self):
        """Return the temperature."""
        temperature = self.data_element.findtext(
            './currentConditions/temperature')
        if temperature:
            return float(temperature)
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self):
        """Return the humidity."""
        humidity = self.data_element.findtext(
            './currentConditions/relativeHumidity')
        if humidity:
            return float(humidity)
        return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        wind_speed = self.data_element.findtext(
            './currentConditions/wind/speed')
        if wind_speed:
            return float(wind_speed)
        return None

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        wind_bearing = self.data_element.findtext(
            './currentConditions/wind/bearing')
        if wind_bearing:
            return float(wind_bearing)
        return None

    @property
    def pressure(self):
        """Return the pressure."""
        pressure = self.data_element.findtext(
            './currentConditions/pressure')
        if pressure:
            return 10 * float(pressure)
        return None

    @property
    def visibility(self):
        """Return the visibility."""
        visibility = self.data_element.findtext(
            './currentConditions/relativeHumidity')
        if visibility:
            return float(visibility)
        return None

    @property
    def condition(self):
        """Return the weather condition."""
        icon_code = self.data_element.findtext('./currentConditions/iconCode')
        if icon_code:
            return icon_code_to_condition(int(icon_code))
        else:
            condition = self.data_element.findtext(
                './currentConditions/condition')
            if condition:
                return condition
        return 'Condition not observed'

    @property
    def forecast(self):
        """Return the forecast array."""
        return get_forecast(self.data_element, self.forecast_type)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Environment Canada."""
        self.data_object.update()
        self.data_element = self.data_object.data


def get_forecast(data_element, forecast_type):
    """Build the forecast array."""
    forecast_array = []

    forecast_time = data_element.findtext('./forecastGroup/dateTime/timeStamp')
    if forecast_time is None:
        return forecast_array

    ref_time = datetime.datetime.strptime(forecast_time, '%Y%m%d%H%M%S')

    if forecast_type == 'daily':
        half_days = data_element.findall('./forecastGroup/forecast')
        if 'High' in half_days[0].findtext('./temperatures/textSummary'):
            forecast_array.append({
                ATTR_FORECAST_TIME: ref_time.isoformat(),
                ATTR_FORECAST_TEMP: int(half_days[0].findtext(
                    './temperatures/temperature')),
                ATTR_FORECAST_TEMP_LOW: int(half_days[1].findtext(
                    './temperatures/temperature')),
                ATTR_FORECAST_CONDITION: icon_code_to_condition(
                    int(half_days[0].findtext(
                        './abbreviatedForecast/iconCode')))
            })
            half_days = half_days[2:]
        else:
            half_days = half_days[1:]

        for day, high, low in zip(range(1, 6),
                                  range(0, 9, 2),
                                  range(1, 10, 2)):
            forecast_array.append({
                ATTR_FORECAST_TIME:
                    (ref_time + datetime.timedelta(days=day)).isoformat(),
                ATTR_FORECAST_TEMP: int(half_days[high].findtext(
                    './temperatures/temperature')),
                ATTR_FORECAST_TEMP_LOW: int(half_days[low].findtext(
                    './temperatures/temperature')),
                ATTR_FORECAST_CONDITION: icon_code_to_condition(
                    int(half_days[high].findtext(
                        './abbreviatedForecast/iconCode')))
            })

    elif forecast_type == 'hourly':
        hours = data_element.findall('./hourlyForecastGroup/hourlyForecast')
        for hour in range(0, 24):
            forecast_array.append({
                ATTR_FORECAST_TIME: datetime.datetime.strptime(
                    hours[hour].attrib['dateTimeUTC'],
                    '%Y%m%d%H%M').astimezone().isoformat(),
                ATTR_FORECAST_TEMP: int(hours[hour].findtext('./temperature')),
                ATTR_FORECAST_CONDITION: icon_code_to_condition(
                    int(hours[hour].findtext('./iconCode')))
            })

    return forecast_array


def icon_code_to_condition(icon_code):
    """Return the condition corresponding to an icon code."""
    for condition, codes in ICON_CONDITION_MAP.items():
        if icon_code in codes:
            return condition
    return None
