"""
homeassistant.components.sensor.yr
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Yr.no weather service.

Configuration:

Will show a symbol for the current weather as default:
sensor:
  platform: yr

Will show temperatue and wind direction:
sensor:
  platform: yr
  monitored_conditions:
    - temperature
    - windDirection

"""
import logging
import datetime
import urllib.request
import xmltodict

from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Sensor types are defined like so:
SENSOR_TYPES = {
    'symbol': ['Symbol', ''],
    'precipitation': ['Condition', ''],
    'temperature': ['Temperature', '°C'],
    'windSpeed': ['Wind speed', 'm/s'],
    'pressure': ['Pressure', 'hPa'],
    'windDirection': ['Wind direction', '°'],
    'humidity': ['Humidity', ''],
    'fog': ['Fog', '%'],
    'cloudiness': ['Cloudiness', '%'],
    'lowClouds': ['Low clouds', '%'],
    'mediumClouds': ['Medium clouds', '%'],
    'highClouds': ['High clouds', '%'],
    'dewpointTemperature': ['Dewpoint temperature', '°C'],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the yr.no sensor. """

    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    from astral import Location, GoogleGeocoder

    location = Location(('', '', hass.config.latitude, hass.config.longitude,
                         hass.config.time_zone, 0))

    google = GoogleGeocoder()
    try:
        google._get_elevation(location)  # pylint: disable=protected-access
        _LOGGER.info(
            'Retrieved elevation from Google: %s', location.elevation)
        elevation = location.elevation
    except urllib.error.URLError:
        # If no internet connection available etc.
        elevation = 0

    coordinates = dict(lat=hass.config.latitude,
                       lon=hass.config.longitude, msl=elevation)

    dev = []
    if 'monitored_conditions' in config:
        for variable in config['monitored_conditions']:
            if variable not in SENSOR_TYPES:
                _LOGGER.error('Sensor type: "%s" does not exist', variable)
            else:
                dev.append(YrSensor(coordinates, variable))

    if len(dev) == 0:
        dev.append(YrSensor(coordinates, "symbol"))
    add_devices(dev)


# pylint: disable=too-many-instance-attributes
class YrSensor(Entity):
    """ Implements an Yr.no sensor. """

    def __init__(self, coordinates, sensor_type):
        self.client_name = ''
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self._weather_data = None

        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._nextrun = datetime.datetime.fromtimestamp(0)
        self._url = 'http://api.yr.no/weatherapi/locationforecast/1.9/?' \
            'lat={lat};lon={lon};msl={msl}'.format(**coordinates)

        self.update()

    @property
    def name(self):
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def state_attributes(self):
        """ Returns state attributes. """
        data = {}
        data[''] = "Weather forecast from yr.no, delivered by the"\
            " Norwegian Meteorological Institute and the NRK"
        if self.type == 'symbol':
            symbol_nr = self._state
            data[ATTR_ENTITY_PICTURE] = "http://api.met.no/weatherapi/weathericon/1.1/" \
                                        "?symbol=" + str(symbol_nr) + \
                                        ";content_type=image/png"
        return data

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self._unit_of_measurement

    # pylint: disable=too-many-branches
    def update(self):
        """ Gets the latest data from yr.no and updates the states. """
        if datetime.datetime.now() > self._nextrun:
            try:
                response = urllib.request.urlopen(self._url)
            except urllib.error.URLError:
                return
            if response.status != 200:
                return
            _data = response.read().decode('utf-8')
            self._weather_data = xmltodict.parse(_data)['weatherdata']
            model = self._weather_data['meta']['model']
            if '@nextrun' not in model:
                model = model[0]
            self._nextrun = datetime.datetime.strptime(model['@nextrun'],
                                                       "%Y-%m-%dT%H:%M:%SZ")
            time_data = self._weather_data['product']['time']

            for k in range(len(self._weather_data['product']['time'])):
                temp_data = time_data[k]['location']
                if self.type in temp_data:
                    if self.type == 'precipitation':
                        self._state = temp_data[self.type]['@value']
                    elif self.type == 'temperature':
                        self._state = temp_data[self.type]['@value']
                    elif self.type == 'windSpeed':
                        self._state = temp_data[self.type]['@mps']
                    elif self.type == 'pressure':
                        self._state = temp_data[self.type]['@value']
                    elif self.type == 'windDirection':
                        self._state = float(temp_data[self.type]['@deg'])
                    elif self.type == 'humidity':
                        self._state = temp_data[self.type]['@value']
                    elif self.type == 'fog':
                        self._state = temp_data[self.type]['@percent']
                    elif self.type == 'cloudiness':
                        self._state = temp_data[self.type]['@percent']
                    elif self.type == 'lowClouds':
                        self._state = temp_data[self.type]['@percent']
                    elif self.type == 'mediumClouds':
                        self._state = temp_data[self.type]['@percent']
                    elif self.type == 'highClouds':
                        self._state = temp_data[self.type]['@percent']
                    elif self.type == 'dewpointTemperature':
                        self._state = temp_data[self.type]['@value']
                    elif self.type == 'symbol':
                        self._state = temp_data[self.type]['@number']
                    return
