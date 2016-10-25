"""
Trenitalia sensor.

This simple sensor uses ViaggiaTreno APIs to provide information about Italian public railroads
status.
"""
import datetime
import logging
import urllib.request
import json
import re
import voluptuous as vol
from urllib.parse import quote, urljoin

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

CONF_STATION_NAME = 'station_name'
CONF_TRAIN_NO = 'train_no'
CONF_ORIGIN_STATION = 'origin_station'
CONF_ATTRIBUTION = 'Data provided by ViaggiaTreno.it'
ICON = 'mdi:train'
RESOURCE_URL = "http://www.viaggiatreno.it/viaggiatrenonew/resteasy/viaggiatreno/"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION_NAME): cv.string,
    vol.Required(CONF_TRAIN_NO): cv.string,
    vol.Optional(CONF_ORIGIN_STATION): cv.string,
})

def get_origin_station(train_no):
    """Get station id from train number."""
    url = urljoin(RESOURCE_URL, "cercaNumeroTrenoTrenoAutocomplete/{}".format(train_no))
    r = urllib.request.urlopen(url)
    content = r.read().decode('utf-8')
    m = re.search('.*\|\d*-(.*)', content)
    return m.group(1)

def get_station_id(station_name):
    """Retrieve station ID by exact name match."""
    url = urljoin(RESOURCE_URL, "autocompletaStazione/{}".format(quote(station_name.upper())))
    r = urllib.request.urlopen(url)
    # Get only first match
    content = r.read().decode('utf-8').split('\n')[0]
    if not content:
        _LOGGER.error('Cannot retrieve data for station: {}'.format(station_name))
        raise Exception
    m = re.search('.*\|(.*)', content)
    return m.group(1)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Viaggiatreno sensor."""
    station_name = config.get(CONF_STATION_NAME)
    train_no = config.get(CONF_TRAIN_NO)
    if config.get(CONF_ORIGIN_STATION):
        origin_station = config.get(CONF_ORIGIN_STATION)
    else:
        origin_station = get_origin_station(train_no)
    add_devices([ViaggiatrenoSensor(station_name, train_no, origin_station)])

class ViaggiatrenoSensor(Entity):
    """Implements Viaggiatreno sensor."""
    
    def __init__(self, station_name, train_no, origin_station):
        """Sensor initialization."""
        self.train_no = train_no
        self.station_name = station_name
        self.station_id = get_station_id(station_name)
        self.origin_station = origin_station
        self._unit_of_measurement = 'min'
        self._state = self.update()
        self._name = "Train {} h: {} at {}".format(train_no, self.programmed_arrival, station_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return icon for the frontend."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return the unit this sensor is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the current delay for the train."""
        return self._state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Actually updates data."""
        url = urljoin(RESOURCE_URL, "tratteCanvas/{}/{}".format(self.origin_station, self.train_no))
        r = urllib.request.urlopen(url)
        data = json.loads(r.read().decode('utf-8'))
        station = [x['fermata'] for x in data if x['fermata']['id'] == str(self.station_id)][0]
        h = station['programmata']
        self.programmed_arrival = datetime.datetime.fromtimestamp(h/1000).strftime('%H:%M:%S')
        delay = station['ritardo']
        # If the train is already passed return None
        if datetime.datetime.fromtimestamp(station['programmata']/1000) < datetime.datetime.now():
            return None
        else:
            return delay
