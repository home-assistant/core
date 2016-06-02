"""
Support for Forecast.io weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.forecast/
"""
import logging
from datetime import timedelta
from requests.exceptions import ConnectionError as ConnectError, \
    HTTPError, Timeout

from homeassistant.const import CONF_API_KEY, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['python-forecastio==1.3.4']
_LOGGER = logging.getLogger(__name__)

# Sensor types are defined like so:
# Name, si unit, us unit, ca unit, uk unit, uk2 unit
SENSOR_TYPES = {
    'summary': ['Summary', None, None, None, None, None],
    'minutely_summary': ['Minutely Summary', None, None, None, None, None],
    'hourly_summary': ['Hourly Summary', None, None, None, None, None],
    'daily_summary': ['Daily Summary', None, None, None, None, None],
    'icon': ['Icon', None, None, None, None, None],
    'nearest_storm_distance': ['Nearest Storm Distance',
                               'km', 'm', 'km', 'km', 'm'],
    'nearest_storm_bearing': ['Nearest Storm Bearing',
                              '°', '°', '°', '°', '°'],
    'precip_type': ['Precip', None, None, None, None, None],
    'precip_intensity': ['Precip Intensity', 'mm', 'in', 'mm', 'mm', 'mm'],
    'precip_probability': ['Precip Probability', '%', '%', '%', '%', '%'],
    'temperature': ['Temperature', '°C', '°F', '°C', '°C', '°C'],
    'apparent_temperature': ['Apparent Temperature',
                             '°C', '°F', '°C', '°C', '°C'],
    'dew_point': ['Dew point', '°C', '°F', '°C', '°C', '°C'],
    'wind_speed': ['Wind Speed', 'm/s', 'mph', 'km/h', 'mph', 'mph'],
    'wind_bearing': ['Wind Bearing', '°', '°', '°', '°', '°'],
    'cloud_cover': ['Cloud Coverage', '%', '%', '%', '%', '%'],
    'humidity': ['Humidity', '%', '%', '%', '%', '%'],
    'pressure': ['Pressure', 'mbar', 'mbar', 'mbar', 'mbar', 'mbar'],
    'visibility': ['Visibility', 'km', 'm', 'km', 'km', 'm'],
    'ozone': ['Ozone', 'DU', 'DU', 'DU', 'DU', 'DU'],
}

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Forecast.io sensor."""
    api_key = config.get(CONF_API_KEY, None)
    if None in (hass.config.latitude, hass.config.longitude, api_key):
        _LOGGER.error("Latitude, longitude, or API key missing from config")
        return False

    if 'units' in config:
        units = config['units']
    elif hass.config.temperature_unit == TEMP_CELSIUS:
        units = 'si'
    else:
        units = 'us'

    try:
        data = ForeCastData(api_key, hass.config.latitude,
                            hass.config.longitude, units)
        data.update_currently()
    except ValueError as error:
        _LOGGER.error(error)
        return False

    sensors = []
    for variable in config['monitored_conditions']:
        if variable in SENSOR_TYPES:
            sensors.append(ForeCastSensor(data, variable))
        else:
            _LOGGER.error('Sensor type: "%s" does not exist', variable)

    add_devices(sensors)


# pylint: disable=too-few-public-methods
class ForeCastSensor(Entity):
    """Implementation of a Forecast.io sensor."""

    def __init__(self, weather_data, sensor_type):
        """Initialize the sensor."""
        self.client_name = 'Weather'
        self._name = SENSOR_TYPES[sensor_type][0]
        self.sdk = weather_data
        self.type = sensor_type
        self._state = None

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        self.sdk.update_unit_of_measurement(self.type)
        return self.sdk.unit_of_measurement

    @property
    def unit_system(self):
        """Return the unit system of this entity."""
        return self.sdk.unit_system

    # pylint: disable=too-many-branches,too-many-statements
    def update(self):
        """Get the latest data from Forecast.io and updates the states."""
        import forecastio

        self.sdk.update()

        try:
            if self.type == 'minutely_summary':
                self.sdk.update_minutely()
                self._state = self.sdk.data_minutely.summary
                return

            elif self.type == 'hourly_summary':
                self.sdk.update_hourly()
                self._state = self.sdk.data_hourly.summary
                return

            elif self.type == 'daily_summary':
                self.sdk.update_daily()
                self._state = self.sdk.data_daily.summary
                return

        except forecastio.utils.PropertyUnavailable:
            return

        self.sdk.update_currently()
        data = self.sdk.data_currently

        try:
            if self.type == 'summary':
                self._state = data.summary
            elif self.type == 'icon':
                self._state = data.icon
            elif self.type == 'nearest_storm_distance':
                self._state = data.nearestStormDistance
            elif self.type == 'nearest_storm_bearing':
                self._state = data.nearestStormBearing
            elif self.type == 'precip_intensity':
                self._state = data.precipIntensity
            elif self.type == 'precip_type':
                self._state = data.precipType
            elif self.type == 'precip_probability':
                self._state = round(data.precipProbability * 100, 1)
            elif self.type == 'dew_point':
                self._state = round(data.dewPoint, 1)
            elif self.type == 'temperature':
                self._state = round(data.temperature, 1)
            elif self.type == 'apparent_temperature':
                self._state = round(data.apparentTemperature, 1)
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
    """Gets the latest data from Forecast.io."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, api_key, latitude, longitude, units):
        """Initialize the data object."""
        self._api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.units = units

        self.data = None
        self.unit_system = None
        self.unit_of_measurement = None
        self.data_currently = None
        self.data_minutely = None
        self.data_hourly = None
        self.data_daily = None

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Forecast.io."""
        import forecastio

        try:
            self.data = forecastio.load_forecast(self._api_key,
                                                 self.latitude,
                                                 self.longitude,
                                                 units=self.units)
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            raise ValueError("Unable to init Forecast.io. - %s", error)
        self.unit_system = self.data.json['flags']['units']

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_currently(self):
        """Update currently data."""
        self.data_currently = self.data.currently()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_minutely(self):
        """Update minutely data."""
        self.data_minutely = self.data.minutely()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_hourly(self):
        """Update hourly data."""
        self.data_hourly = self.data.hourly()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_daily(self):
        """Update daily data."""
        self.data_daily = self.data.daily()

    def update_unit_of_measurement(self, sensor_type):
        """Update units based on unit system."""
        if self.unit_system == 'si':
            self.unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        elif self.unit_system == 'us':
            self.unit_of_measurement = SENSOR_TYPES[sensor_type][2]
        elif self.unit_system == 'ca':
            self.unit_of_measurement = SENSOR_TYPES[sensor_type][3]
        elif self.unit_system == 'uk':
            self.unit_of_measurement = SENSOR_TYPES[sensor_type][4]
        elif self.unit_system == 'uk2':
            self.unit_of_measurement = SENSOR_TYPES[sensor_type][5]
        else:
            self.unit_of_measurement = None
