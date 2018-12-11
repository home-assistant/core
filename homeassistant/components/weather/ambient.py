"""
Platform to pull data from Ambient Weather networkself.

Note that Ambient only reports data from a local weather station.
There are no forecasts.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/ambient/
"""
from collections import namedtuple
from datetime import timedelta
import logging

from requests.exceptions import (
    ConnectionError as ConnectError, HTTPError, Timeout)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_OZONE, ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE, ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED, WeatherEntity)
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, PRECISION_TENTHS, TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.temperature import display_temp

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['ambient_api']
DEFAULT_NAME = "Ambient Weather"

SCAN_INTERVAL = timedelta(minutes=5)

CONDITION_CLASSES = {
    'cloudy': [],
    'fog': [],
    'hail': [],
    'lightning': [],
    'lightning-rainy': [],
    'partlycloudy': [],
    'pouring': [],
    'rainy': ['shower rain'],
    'snowy': [],
    'snowy-rainy': [],
    'sunny': ['sunshine'],
    'windy': [],
    'windy-variant': [],
    'exceptional': [],
}

# Additional Ambient data fields
ATTR_SOLAR_RADIATION = 'solar_radiation'
ATTR_WIND_GUST = 'wind_gust'
ATTR_HOURLY_RAIN = 'hourly_rain'
ATTR_DAILY_RAIN = 'daily_rain'
ATTR_FEELS_LIKE = 'feels_like'

KEY_ORDER = [ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_OZONE, ATTR_WEATHER_PRESSURE,
             ATTR_WEATHER_TEMPERATURE, ATTR_FEELS_LIKE,
             ATTR_WEATHER_WIND_BEARING, ATTR_WEATHER_WIND_SPEED,
             ATTR_WIND_GUST, ATTR_SOLAR_RADIATION, ATTR_HOURLY_RAIN,
             ATTR_DAILY_RAIN]

JSON_KEYS = {ATTR_WEATHER_HUMIDITY: 'humidity', ATTR_WEATHER_OZONE: 'uv',
             ATTR_WEATHER_PRESSURE: 'baromrelin',
             ATTR_WEATHER_TEMPERATURE: 'tempf', ATTR_FEELS_LIKE: 'feelsLike',
             ATTR_WEATHER_WIND_BEARING: 'winddir',
             ATTR_WEATHER_WIND_SPEED: 'windspeedmph',
             ATTR_WIND_GUST: 'windgustmph',
             ATTR_SOLAR_RADIATION: 'solarradiation',
             ATTR_HOURLY_RAIN: 'hourlyrainin',
             ATTR_DAILY_RAIN: 'dailyrainin'}

TEMPERATURE_KEYS = [ATTR_WEATHER_TEMPERATURE, ATTR_FEELS_LIKE]
VELOCITY_KEYS = [ATTR_WEATHER_WIND_SPEED, ATTR_WIND_GUST]
LENGTH_KEYS = [ATTR_HOURLY_RAIN, ATTR_DAILY_RAIN]

MPH_TO_KPH = 1.60934
IN_TO_CM = 2.54

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

APPLICATION_KEY = ('ad5fc285e0ee47549b3d49a48b0ef9b7df1' +
                   'eba79e837465584f89dcceb938a3f')

AMBIENT_URL = 'https://api.ambientweather.net/v1'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Initialize Ambient data object and entity."""
    from ambient_api.ambientapi import AmbientAPI

    api_key = config.get(CONF_API_KEY)
    name = config.get(CONF_NAME)
    ambient_api = AmbientAPI(AMBIENT_ENDPOINT=AMBIENT_URL,
                             AMBIENT_API_KEY=api_key,
                             AMBIENT_APPLICATION_KEY=APPLICATION_KEY,
                             log_level=_LOGGER.getEffectiveLevel())

    ambient = AmbientData(hass, ambient_api)

    add_entities([AmbientWeather(hass, name, ambient)])


class AmbientWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, hass, name, ambient):
        """Initialize the Demo weather."""
        self.hass = hass
        self._name = name
        self._ambient = ambient
        self._ambient.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """Set polling to true."""
        return True

    @property
    def temperature(self):
        """Return the temperature."""
        if self._ambient.adoutput is not None:
            return self._ambient.adoutput.temperature
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self.hass.config.units.temperature_unit

    @property
    def humidity(self):
        """Return the humidity."""
        if self._ambient.adoutput is not None:
            return self._ambient.adoutput.humidity
        return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        if self._ambient.adoutput is not None:
            return self._ambient.adoutput.wind_speed
        return None

    @property
    def wind_bearing(self):
        """Return the wind speed."""
        if self._ambient.adoutput is not None:
            return self._ambient.adoutput.wind_bearing
        return None

    @property
    def pressure(self):
        """Return the pressure."""
        if self._ambient.adoutput is not None:
            return self._ambient.adoutput.pressure
        return None

    @property
    def condition(self):
        """Return the weather condition."""
        if self._ambient.adoutput.hourly_rain > 0.1:
            return 'pouring'

        if self._ambient.adoutput.hourly_rain > 0:
            return 'rainy'

        if self._ambient.adoutput.daily_rain > 0:
            return 'cloudy'

        if self._ambient.adoutput.wind_gust > 15:
            return 'windy'

        if self._ambient.adoutput.solar_radiation >= 100:
            return 'sunny'

        return None

    @property
    def ozone(self):
        """Return the ozone level."""
        return self._ambient.adoutput.ozone

    @property
    def attribution(self):
        """Return the attribution."""
        attr_str = 'Data from Ambient Weather'
        return attr_str

    @property
    def forecast(self):
        """Return the forecast. Ambient doesn't support this."""
        return None

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self._ambient.adoutput is None:
            return None

        data = {}
        for key in range(len(KEY_ORDER)):
            data[KEY_ORDER[key]] = self._ambient.adoutput[key]

        return data

    def update(self):
        """Update the data by delegating to the data object."""
        self._ambient.update()


class AmbientData:
    """Helper object to retrieve Ambient data."""

    def __init__(self, hass, api):
        """Set up the http session and data structures."""
        self.hass = hass
        self.api = api
        self._data = namedtuple(
            'status', KEY_ORDER
            )
        self.adoutput = None

    def mph_to_kph(self, value_mph):
        """Convert mph to metric if required."""
        conv_mph = value_mph
        if self.hass.config.units.is_metric:
            conv_mph = round(conv_mph * MPH_TO_KPH, 1)
        return conv_mph

    def in_to_cm(self, value_in):
        """Convert inches to metric if required."""
        conv_in = value_in
        if self.hass.config.units.is_metric:
            conv_in = round(conv_in * IN_TO_CM, 2)
        return conv_in

    def update(self):
        """Retrieve the data from Ambient and decode."""
        try:
            devices = self.api.get_devices()

            payload = devices[0].last_data
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("Payload: %s", payload)

            named_list = []

            for name_key in KEY_ORDER:
                json_key = JSON_KEYS.get(name_key)
                if json_key in payload:
                    value = float(payload.get(json_key))
                    if name_key in TEMPERATURE_KEYS:
                        value = display_temp(self.hass, value, TEMP_FAHRENHEIT,
                                             PRECISION_TENTHS)
                    if name_key in VELOCITY_KEYS:
                        value = self.mph_to_kph(value)
                    if name_key in LENGTH_KEYS:
                        value = self.in_to_cm(value)
                    named_list.append(value)
                else:
                    named_list.append(0.0)

            self.adoutput = self._data._make(named_list)

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("Retrieved ambient data %s", self.adoutput)
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            _LOGGER.error("Unable to connect to Dark Sky. %s", error)
            self.adoutput = None
