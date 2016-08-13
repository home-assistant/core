"""
Support for the OpenWeatherMap (OWM) service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.openweathermap/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (CONF_API_KEY, TEMP_CELSIUS, TEMP_FAHRENHEIT,
                                 CONF_PLATFORM, CONF_MONITORED_CONDITIONS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pyowm==2.3.2']
_LOGGER = logging.getLogger(__name__)
SENSOR_TYPES = {
    'weather': ['Condition', None],
    'temperature': ['Temperature', None],
    'wind_speed': ['Wind speed', 'm/s'],
    'humidity': ['Humidity', '%'],
    'pressure': ['Pressure', 'mbar'],
    'clouds': ['Cloud coverage', '%'],
    'rain': ['Rain', 'mm'],
    'snow': ['Snow', 'mm']
}

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'openweathermap',
    vol.Required(CONF_API_KEY): vol.Coerce(str),
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
        [vol.In(SENSOR_TYPES.keys())],
    vol.Optional('forecast', default=False): cv.boolean
})

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the OpenWeatherMap sensor."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    from pyowm import OWM

    SENSOR_TYPES['temperature'][1] = hass.config.units.temperature_unit
    forecast = config.get('forecast')
    owm = OWM(config.get(CONF_API_KEY, None))

    if not owm:
        _LOGGER.error(
            "Connection error "
            "Please check your settings for OpenWeatherMap.")
        return False

    data = WeatherData(owm, forecast, hass.config.latitude,
                       hass.config.longitude)
    dev = []
    try:
        for variable in config['monitored_conditions']:
            if variable not in SENSOR_TYPES:
                _LOGGER.error('Sensor type: "%s" does not exist', variable)
            else:
                dev.append(OpenWeatherMapSensor(data, variable,
                                                SENSOR_TYPES[variable][1]))
    except KeyError:
        pass

    if forecast:
        SENSOR_TYPES['forecast'] = ['Forecast', None]
        dev.append(OpenWeatherMapSensor(data, 'forecast',
                                        SENSOR_TYPES['temperature'][1]))

    add_devices(dev)


# pylint: disable=too-few-public-methods, too-many-instance-attributes
class OpenWeatherMapSensor(Entity):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(self, weather_data, sensor_type, temp_unit):
        """Initialize the sensor."""
        self.client_name = 'Weather'
        self._name = SENSOR_TYPES[sensor_type][0]
        self.owa_client = weather_data
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._weather_code = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        # pylint: disable=too-many-return-statements, too-many-branches
        if self.type != 'weather' or self._weather_code is None:
            return None

        # See: http://openweathermap.org/weather-conditions

        # Group 2xx: Thunderstorm
        if 200 <= self._weather_code < 300:
            if self._weather_code in (200, 201, 202, 230, 231, 232):
                return 'mdi:weather-lightning-rainy'
            else:
                return 'mdi:weather-lightning'

        # Group 3xx: Drizzle
        if 300 <= self._weather_code < 400:
            return 'mdi:weather-rainy'

        # Group 5xx: Rain
        if 500 <= self._weather_code < 600:
            if self._weather_code in (502, 503, 504):
                return 'mdi:weather-pouring'
            elif self._weather_code == 511:
                return 'mdi:weather-snowy-rainy'
            else:
                return 'mdi:weather-rainy'

        # Group 6xx: Snow
        if 600 <= self._weather_code < 700:
            if self._weather_code in (611, 612, 615, 616, 620, 621, 622):
                return 'mdi:weather-snowy-rainy'
            else:
                return 'mdi:weather-snowy'

        # Group 7xx: Atmosphere
        if 700 <= self._weather_code < 800:
            if self._weather_code in (701, 711, 721, 741):
                return 'mdi:weather-fog'
            elif self._weather_code == 771:
                return 'mdi:weather-windy'

        # Group 800: Clear
        if self._weather_code == 800:
            return 'mdi:weather-sunny'

        # Group 80x: Clouds
        if 801 <= self._weather_code < 810:
            if self._weather_code in (801, 802):
                return 'mdi:weather-partlycloudy'
            else:
                return 'mdi:weather-cloudy'

        # Group 90x: Extreme
        if 900 <= self._weather_code < 910:
            if self._weather_code == 905:
                return 'mdi:weather-windy'
            elif self._weather_code == 906:
                return 'mdi:weather-hail'

        # Group 9xx: Additional
        if 910 <= self._weather_code < 1000:
            if self._weather_code in (951, 952, 953):
                return 'mdi:weather-sunny'
            elif self._weather_code in (954, 955, 956, 957, 958, 959):
                return 'mdi:weather-windy'
            elif self._weather_code in (960, 961):
                return 'mdi:weather-lightning'

        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data from OWM and updates the states."""
        self.owa_client.update()
        data = self.owa_client.data
        fc_data = self.owa_client.fc_data

        if self.type == 'weather':
            self._state = data.get_detailed_status()
            self._weather_code = data.get_weather_code()
        elif self.type == 'temperature':
            if self.temp_unit == TEMP_CELSIUS:
                self._state = round(data.get_temperature('celsius')['temp'],
                                    1)
            elif self.temp_unit == TEMP_FAHRENHEIT:
                self._state = round(data.get_temperature('fahrenheit')['temp'],
                                    1)
            else:
                self._state = round(data.get_temperature()['temp'], 1)
        elif self.type == 'wind_speed':
            self._state = round(data.get_wind()['speed'], 1)
        elif self.type == 'humidity':
            self._state = round(data.get_humidity(), 1)
        elif self.type == 'pressure':
            self._state = round(data.get_pressure()['press'], 0)
        elif self.type == 'clouds':
            self._state = data.get_clouds()
        elif self.type == 'rain':
            if data.get_rain():
                self._state = round(data.get_rain()['3h'], 0)
                self._unit_of_measurement = 'mm'
            else:
                self._state = 'not raining'
                self._unit_of_measurement = ''
        elif self.type == 'snow':
            if data.get_snow():
                self._state = round(data.get_snow(), 0)
                self._unit_of_measurement = 'mm'
            else:
                self._state = 'not snowing'
                self._unit_of_measurement = ''
        elif self.type == 'forecast':
            self._state = fc_data.get_weathers()[0].get_status()


class WeatherData(object):
    """Get the latest data from OpenWeatherMap."""

    def __init__(self, owm, forecast, latitude, longitude):
        """Initialize the data object."""
        self.owm = owm
        self.forecast = forecast
        self.latitude = latitude
        self.longitude = longitude
        self.data = None
        self.fc_data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from OpenWeatherMap."""
        obs = self.owm.weather_at_coords(self.latitude, self.longitude)
        if obs is None:
            _LOGGER.warning('Failed to fetch data from OWM')
            return

        self.data = obs.get_weather()

        if self.forecast == 1:
            obs = self.owm.three_hours_forecast_at_coords(self.latitude,
                                                          self.longitude)
            self.fc_data = obs.get_forecast()
