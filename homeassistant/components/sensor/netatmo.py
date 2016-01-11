"""
homeassistant.components.sensor.netatmo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This sensor connects to the cloud service provided by netatmo and uses
the api.
To successfully connect it needs the client_id and client_secret from
a netatmo developer account and your username and password from the
netatmo user account
"""
from datetime import timedelta
import logging
import requests

from homeassistant.const import (STATE_UNKNOWN)
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_CELCIUS, CONF_USERNAME, CONF_PASSWORD

SENSOR_TYPES = {
    'Temperature': [TEMP_CELCIUS],
    'Humidity': ['%'],
    'CO2': ['ppm'],
    'Noise': ['dB'],
    'Pressure': ['mBar']
}

SENSOR_URL = "https://api.netatmo.com//api/getstationsdata?access_token="
_LOGGER = logging.getLogger(__name__)

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

CONF_ID = 'client_id'
CONF_SECRET = 'client_secret'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Gets a list of the available stations and sets up the sensors. """

    client_id = config.get(CONF_ID, None)
    client_secret = config.get(CONF_SECRET, None)
    username = config.get(CONF_USERNAME, None)
    password = config.get(CONF_PASSWORD, None)
    if None in (client_id, client_secret, username, password):
        _LOGGER.error('Not all required config keys present: %s',
                      ', '.join((CONF_ID, CONF_SECRET,
                                 CONF_USERNAME, CONF_PASSWORD)))
        return False
    cred = {CONF_ID: client_id, CONF_SECRET: client_secret,
            CONF_USERNAME: username, CONF_PASSWORD: password}
    dev = list()
    request = requests.post("https://api.netatmo.net/oauth2/token",
                            data={'grant_type': 'password',
                                  'client_id': client_id,
                                  'client_secret': client_secret,
                                  'username': username,
                                  'password': password}, timeout=10)
    request = requests.get(SENSOR_URL + request.json()["access_token"],
                           timeout=10).json()
    data = NetatmoData(cred)
    for device in request["body"]["devices"]:
        for data_type in device["data_type"]:
            dev.append(NetatmoSensor(hass, data, data_type,
                                     device["module_name"]))
        for module in device["modules"]:
            for data_type in module["data_type"]:
                dev.append(NetatmoSensor(hass, data, data_type,
                                         module["module_name"]))
    add_devices(dev)


class NetatmoData(object):
    """ Connects to the Netatmo api and holds data for sensors. """

    def __init__(self, cred):
        self._cred = cred
        self._request = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Connects to the Netatmo server end updates the sensor. """
        token = requests.post("https://api.netatmo.net/oauth2/token",
                              data={'grant_type': 'password',
                                    'client_id': self._cred[CONF_ID],
                                    'client_secret': self._cred[CONF_SECRET],
                                    'username': self._cred[CONF_USERNAME],
                                    'password': self._cred[CONF_PASSWORD]},
                              timeout=10)
        self._request = requests.get(SENSOR_URL + token.json()["access_token"],
                                     timeout=10).json()

    def data(self):
        """ Returns the last request data. """
        return self._request


class NetatmoSensor(Entity):
    """ Implements a netatmo sensor and parses the data gotten from
    the data class. """

    def __init__(self, hass, data, data_type, module_name):
        self._hass = hass
        self._data = data
        self._state = STATE_UNKNOWN
        self._data_type = data_type
        self._name = module_name
        self._unit_of_measurement = SENSOR_TYPES[data_type][0]
        self.update()

    @property
    def name(self):
        """ The name of the sensor. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return self._unit_of_measurement

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    def update(self):
        """ Gets the latest data from Netatmo API and updates the state. """
        self._data.update()
        request = self._data.data()
        for device in request["body"]["devices"]:
            if self._name == device["module_name"]:
                self._state = device["dashboard_data"][self._data_type]
            for module in device["modules"]:
                if self._name == module["module_name"]:
                    self._state = module["dashboard_data"][self._data_type]
