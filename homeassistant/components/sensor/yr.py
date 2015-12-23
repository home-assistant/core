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

Will show all available sensors:
sensor:
  platform: yr
  monitored_conditions:
    - temperature
    - symbol
    - precipitation
    - windSpeed
    - pressure
    - windDirection
    - humidity
    - fog
    - cloudiness
    - lowClouds
    - mediumClouds
    - highClouds
    - dewpointTemperature

"""
import logging
import datetime
import urllib.request
import requests

from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


REQUIREMENTS = ['xmltodict', 'astral==0.8.1']

# Sensor types are defined like so:
SENSOR_TYPES = {
    'symbol': ['Symbol', ''],
    'precipitation': ['Condition', 'mm'],
    'temperature': ['Temperature', '°C'],
    'windSpeed': ['Wind speed', 'm/s'],
    'pressure': ['Pressure', 'hPa'],
    'windDirection': ['Wind direction', '°'],
    'humidity': ['Humidity', '%'],
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

    weather = YrData(coordinates)

    dev = []
    if 'monitored_conditions' in config:
        for variable in config['monitored_conditions']:
            if variable not in SENSOR_TYPES:
                _LOGGER.error('Sensor type: "%s" does not exist', variable)
            else:
                dev.append(YrSensor(variable, weather))

    # add symbol as default sensor
    if len(dev) == 0:
        dev.append(YrSensor("symbol", weather))
    add_devices(dev)


# pylint: disable=too-many-instance-attributes
class YrSensor(Entity):
    """ Implements an Yr.no sensor. """

    def __init__(self, sensor_type, weather):
        self.client_name = 'yr'
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self._weather = weather
        self._info = ''
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._update = datetime.datetime.fromtimestamp(0)

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

    @property
    def should_poll(self):
        """ Return True if entity has to be polled for state. """
        return True

    # pylint: disable=too-many-branches, too-many-return-statements
    def update(self):
        """ Gets the latest data from yr.no and updates the states. """

        self._weather.update()
        now = datetime.datetime.now()
        # check if data should be updated
        if now <= self._update:
            return

        time_data = self._weather.data['product']['time']

        # pylint: disable=consider-using-enumerate
        # find sensor
        for k in range(len(time_data)):
            valid_from = datetime.datetime.strptime(time_data[k]['@from'],
                                                    "%Y-%m-%dT%H:%M:%SZ")
            valid_to = datetime.datetime.strptime(time_data[k]['@to'],
                                                  "%Y-%m-%dT%H:%M:%SZ")
            self._update = valid_to
            self._info = "Forecast between " + time_data[k]['@from'] \
                + " and " + time_data[k]['@to'] + ". "

            temp_data = time_data[k]['location']
            if self.type not in temp_data and now >= valid_to:
                continue
            if self.type == 'precipitation' and valid_from < now:
                self._state = temp_data[self.type]['@value']
                return
            elif self.type == 'symbol' and valid_from < now:
                self._state = temp_data[self.type]['@number']
                return
            elif self.type == 'temperature':
                self._state = temp_data[self.type]['@value']
                return
            elif self.type == 'windSpeed':
                self._state = temp_data[self.type]['@mps']
                return
            elif self.type == 'pressure':
                self._state = temp_data[self.type]['@value']
                return
            elif self.type == 'windDirection':
                self._state = float(temp_data[self.type]['@deg'])
                return
            elif self.type == 'humidity':
                self._state = temp_data[self.type]['@value']
                return
            elif self.type == 'fog':
                self._state = temp_data[self.type]['@percent']
                return
            elif self.type == 'cloudiness':
                self._state = temp_data[self.type]['@percent']
                return
            elif self.type == 'lowClouds':
                self._state = temp_data[self.type]['@percent']
                return
            elif self.type == 'mediumClouds':
                self._state = temp_data[self.type]['@percent']
                return
            elif self.type == 'highClouds':
                self._state = temp_data[self.type]['@percent']
                return
            elif self.type == 'dewpointTemperature':
                self._state = temp_data[self.type]['@value']
                return


# pylint: disable=too-few-public-methods
class YrData(object):
    """ Gets the latest data and updates the states. """

    def __init__(self, coordinates):
        self._url = 'http://api.yr.no/weatherapi/locationforecast/1.9/?' \
            'lat={lat};lon={lon};msl={msl}'.format(**coordinates)

        self._nextrun = datetime.datetime.fromtimestamp(0)
        self.update()

    def update(self):
        """ Gets the latest data from yr.no """
        now = datetime.datetime.now()
        # check if new will be available
        if now <= self._nextrun:
            return
        try:
            response = requests.get(self._url)
        except requests.RequestException:
            return
        if response.status_code != 200:
            return
        data = response.text

        import xmltodict
        self.data = xmltodict.parse(data)['weatherdata']
        model = self.data['meta']['model']
        if '@nextrun' not in model:
            model = model[0]
        self._nextrun = datetime.datetime.strptime(model['@nextrun'],
                                                   "%Y-%m-%dT%H:%M:%SZ")
