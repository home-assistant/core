"""Support for the OpenWeatherMap (OWM) service."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION, ATTR_FORECAST_PRECIPITATION, ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_TIME, ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED, PLATFORM_SCHEMA, WeatherEntity)
from homeassistant.const import (
    CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE, CONF_NAME,
    PRESSURE_HPA, PRESSURE_INHG, STATE_UNKNOWN, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.util.pressure import convert as convert_pressure
_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Data provided by OpenWeatherMap'

FORECAST_MODE = ['hourly', 'daily', 'freedaily']

DEFAULT_NAME = 'OpenWeatherMap'

MIN_TIME_BETWEEN_FORECAST_UPDATES = timedelta(minutes=120)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=120)

CONDITION_CLASSES = {
    'cloudy': [803, 804],
    'fog': [701, 741],
    'hail': [906],
    'lightning': [210, 211, 212, 221],
    'lightning-rainy': [200, 201, 202, 230, 231, 232],
    'partlycloudy': [801, 802],
    'pouring': [504, 314, 502, 503, 522],
    'rainy': [300, 301, 302, 310, 311, 312, 313, 500, 501, 520, 521],
    'snowy': [600, 601, 602, 611, 612, 620, 621, 622],
    'snowy-rainy': [511, 615, 616],
    'sunny': [800],
    'windy': [905, 951, 952, 953, 954, 955, 956, 957],
    'windy-variant': [958, 959, 960, 961],
    'exceptional': [711, 721, 731, 751, 761, 762, 771, 900, 901, 962, 903,
                    904],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_MODE, default='hourly'): vol.In(FORECAST_MODE),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the OpenWeatherMap weather platform."""
    import pyowm

    longitude = config.get(CONF_LONGITUDE, round(hass.config.longitude, 5))
    latitude = config.get(CONF_LATITUDE, round(hass.config.latitude, 5))
    name = config.get(CONF_NAME)
    mode = config.get(CONF_MODE)
    # aid-dom
    if config.get(CONF_API_KEY) != "use_ais_dom_api_key":
        try:
            owm = pyowm.OWM(config.get(CONF_API_KEY))
        except pyowm.exceptions.api_call_error.APICallError:
            _LOGGER.error("Error while connecting to OpenWeatherMap")
            return False
    else:
        owm = None

    data = WeatherData(owm, latitude, longitude, mode)

    add_entities([OpenWeatherMapWeather(
        name, data, hass.config.units.temperature_unit, mode)], True)


class OpenWeatherMapWeather(WeatherEntity):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(self, name, owm, temperature_unit, mode):
        """Initialize the sensor."""
        self._name = name
        self._owm = owm
        self._temperature_unit = temperature_unit
        self._mode = mode
        self.data = None
        self.forecast_data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return [k for k, v in CONDITION_CLASSES.items() if
                    self.data.get_weather_code() in v][0]
        except IndexError:
            return STATE_UNKNOWN

    @property
    def temperature(self):
        """Return the temperature."""
        return self.data.get_temperature('celsius').get('temp')

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        pressure = self.data.get_pressure().get('press')
        if self.hass.config.units.name == 'imperial':
            return round(
                convert_pressure(pressure, PRESSURE_HPA, PRESSURE_INHG), 2)
        return pressure

    @property
    def humidity(self):
        """Return the humidity."""
        return self.data.get_humidity()

    @property
    def wind_speed(self):
        """Return the wind speed."""
        if self.hass.config.units.name == 'imperial':
            return round(self.data.get_wind().get('speed') * 2.24, 2)

        return round(self.data.get_wind().get('speed') * 3.6, 2)

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.data.get_wind().get('deg')

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        data = []

        def calc_precipitation(rain, snow):
            """Calculate the precipitation."""
            rain_value = 0 if rain is None else rain
            snow_value = 0 if snow is None else snow
            if round(rain_value + snow_value, 1) == 0:
                return None
            return round(rain_value + snow_value, 1)

        if self._mode == 'freedaily':
            weather = self.forecast_data.get_weathers()[::8]
        else:
            weather = self.forecast_data.get_weathers()

        for entry in weather:
            if self._mode == 'daily':
                data.append({
                    ATTR_FORECAST_TIME:
                        entry.get_reference_time('unix') * 1000,
                    ATTR_FORECAST_TEMP:
                        entry.get_temperature('celsius').get('day'),
                    ATTR_FORECAST_TEMP_LOW:
                        entry.get_temperature('celsius').get('night'),
                    ATTR_FORECAST_PRECIPITATION:
                        calc_precipitation(
                            entry.get_rain().get('all'),
                            entry.get_snow().get('all')),
                    ATTR_FORECAST_WIND_SPEED:
                        entry.get_wind().get('speed'),
                    ATTR_FORECAST_WIND_BEARING:
                        entry.get_wind().get('deg'),
                    ATTR_FORECAST_CONDITION:
                        [k for k, v in CONDITION_CLASSES.items()
                         if entry.get_weather_code() in v][0]
                })
            else:
                data.append({
                    ATTR_FORECAST_TIME:
                        entry.get_reference_time('unix') * 1000,
                    ATTR_FORECAST_TEMP:
                        entry.get_temperature('celsius').get('temp'),
                    ATTR_FORECAST_PRECIPITATION:
                        (round(entry.get_rain().get('3h'), 1)
                         if entry.get_rain().get('3h') is not None
                         and (round(entry.get_rain().get('3h'), 1) > 0)
                         else None),
                    ATTR_FORECAST_CONDITION:
                        [k for k, v in CONDITION_CLASSES.items()
                         if entry.get_weather_code() in v][0]
                })
        return data

    def update(self):
        """Get the latest data from OWM and updates the states."""
        from pyowm.exceptions.api_call_error import APICallError

        try:
            self._owm.update()
            self._owm.update_forecast()
        except APICallError:
            _LOGGER.error("Exception when calling OWM web API to update data")
            return

        self.data = self._owm.data
        self.forecast_data = self._owm.forecast_data


class WeatherData:
    """Get the latest data from OpenWeatherMap."""

    def __init__(self, owm, latitude, longitude, mode):
        """Initialize the data object."""
        self._mode = mode
        self.owm = owm
        self.latitude = latitude
        self.longitude = longitude
        self.data = None
        self.forecast_data = None

    def ais_dom_api(self):
        # aid-dom part
        if not self.owm:
            import pyowm
            try:
                from homeassistant.components import ais_cloud
                aiscloud = ais_cloud.AisCloudWS()
                ws_resp = aiscloud.key("openweathermap_weather")
                json_ws_resp = ws_resp.json()
                try:
                    self.owm = pyowm.OWM(json_ws_resp["key"])
                except pyowm.exceptions.api_call_error.APICallError:
                    _LOGGER.error("Error while connecting to OpenWeatherMap")
            except Exception as error:
                _LOGGER.error("Unable to get the API Key to OpenWeatherMap from AIS dom. %s", error)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        self.ais_dom_api()
        """Get the latest data from OpenWeatherMap."""
        obs = self.owm.weather_at_coords(self.latitude, self.longitude)
        if obs is None:
            _LOGGER.warning("Failed to fetch data from OWM")
            return

        self.data = obs.get_weather()

    @Throttle(MIN_TIME_BETWEEN_FORECAST_UPDATES)
    def update_forecast(self):
        self.ais_dom_api()
        """Get the latest forecast from OpenWeatherMap."""
        from pyowm.exceptions.api_call_error import APICallError

        try:
            if self._mode == 'daily':
                fcd = self.owm.daily_forecast_at_coords(
                    self.latitude, self.longitude, 15)
            else:
                fcd = self.owm.three_hours_forecast_at_coords(
                    self.latitude, self.longitude)
        except APICallError:
            _LOGGER.error("Exception when calling OWM web API "
                          "to update forecast")
            return

        if fcd is None:
            _LOGGER.warning("Failed to fetch forecast data from OWM")
            return

        self.forecast_data = fcd.get_forecast()
