"""
homeassistant.components.sensor.forecast
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Forecast.io service.

Configuration:

To use the Forecast sensor you will need to add something like the
following to your config/configuration.yaml

sensor:
  platform: forecast
  api_key: YOUR_APP_KEY
  monitored_conditions:
    - summary
    - precip_type
    - precip_intensity
    - temperature
    - dew_point
    - wind_speed
    - wind_bearing
    - cloud_cover
    - humidity
    - pressure
    - visibility
    - ozone

Variables:

api_key
*Required
To retrieve this value log into your account at http://forecast.io/. You can
make 1000 requests per day. This means that you could create every 1.4 minute
one.

monitored_conditions
*Required
An array specifying the conditions to monitor.

These are the variables for the monitored_conditions array:

type
*Required
The condition you wish to monitor, see the configuration example above for a
list of all available conditions to monitor.

Details for the API : https://developer.forecast.io/docs/v2
"""
import logging
from datetime import timedelta

REQUIREMENTS = ['python-forecastio==1.3.3']

try:
    import forecastio
except ImportError:
    forecastio = None

from homeassistant.util import Throttle
from homeassistant.const import (CONF_API_KEY, TEMP_CELCIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
SENSOR_TYPES = {
    'summary': ['Summary', ''],
    'precip_type': ['Precip', ''],
    'precip_intensity': ['Precip intensity', 'mm'],
    'temperature': ['Temperature', ''],
    'dew_point': ['Dew point', '°C'],
    'wind_speed': ['Wind Speed', 'm/s'],
    'wind_bearing': ['Wind Bearing', '°'],
    'cloud_cover': ['Cloud coverage', '%'],
    'humidity': ['Humidity', '%'],
    'pressure': ['Pressure', 'mBar'],
    'visibility': ['Visibility', 'km'],
    'ozone': ['Ozone', ''],
}

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the Forecast.io sensor. """

    global forecastio  # pylint: disable=invalid-name
    if forecastio is None:
        import forecastio as forecastio_
        forecastio = forecastio_

    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    SENSOR_TYPES['temperature'][1] = hass.config.temperature_unit
    unit = hass.config.temperature_unit

    try:
        forecast = forecastio.load_forecast(config.get(CONF_API_KEY, None),
                                            hass.config.latitude,
                                            hass.config.longitude)
        forecast.currently()
    except ValueError:
        _LOGGER.error(
            "Connection error "
            "Please check your settings for Forecast.io.")
        return False

    data = ForeCastData(config.get(CONF_API_KEY, None),
                        hass.config.latitude,
                        hass.config.longitude)

    dev = []
    for variable in config['monitored_conditions']:
        if variable not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', variable)
        else:
            dev.append(ForeCastSensor(data, variable, unit))

    add_devices(dev)


# pylint: disable=too-few-public-methods
class ForeCastSensor(Entity):
    """ Implements an Forecast.io sensor. """

    def __init__(self, weather_data, sensor_type, unit):
        self.client_name = 'Weather'
        self._name = SENSOR_TYPES[sensor_type][0]
        self.forecast_client = weather_data
        self._unit = unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self._unit_of_measurement

    # pylint: disable=too-many-branches
    def update(self):
        """ Gets the latest data from Forecast.io and updates the states. """

        self.forecast_client.update()
        data = self.forecast_client.data

        try:
            if self.type == 'summary':
                self._state = data.summary
            elif self.type == 'precip_intensity':
                if data.precipIntensity == 0:
                    self._state = 'None'
                    self._unit_of_measurement = ''
                else:
                    self._state = data.precipIntensity
            elif self.type == 'precip_type':
                if data.precipType is None:
                    self._state = 'None'
                    self._unit_of_measurement = ''
                else:
                    self._state = data.precipType
            elif self.type == 'dew_point':
                if self._unit == TEMP_CELCIUS:
                    self._state = round(data.dewPoint, 1)
                elif self._unit == TEMP_FAHRENHEIT:
                    self._state = round(data.dewPoint * 1.8 + 32.0, 1)
                else:
                    self._state = round(data.dewPoint, 1)
            elif self.type == 'temperature':
                if self._unit == TEMP_CELCIUS:
                    self._state = round(data.temperature, 1)
                elif self._unit == TEMP_FAHRENHEIT:
                    self._state = round(data.temperature * 1.8 + 32.0, 1)
                else:
                    self._state = round(data.temperature, 1)
            elif self.type == 'wind_speed':
                self._state = data.windSpeed
            elif self.type == 'wind_bearing':
                self._state = data.windBearing
            elif self.type == 'cloud_cover':
                self._state = round(data.cloudCover * 100, 1)
            elif self.type == 'humidity':
                self._state = round(data.humidity * 100, 1)
            elif self.type == 'pressure':
                self._state = round(data.pressure, 1)
            elif self.type == 'visibility':
                self._state = data.visibility
            elif self.type == 'ozone':
                self._state = round(data.ozone, 1)
        except forecastio.utils.PropertyUnavailable:
            pass


class ForeCastData(object):
    """ Gets the latest data from Forecast.io. """

    def __init__(self, api_key, latitude, longitude):
        self._api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from Forecast.io. """

        forecast = forecastio.load_forecast(self._api_key,
                                            self.latitude,
                                            self.longitude,
                                            units='si')
        self.data = forecast.currently()
