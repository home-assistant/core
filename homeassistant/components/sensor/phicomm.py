"""
Support for Phicomm air sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.phicomm/
"""

import json
import logging
import os
import requests
import voluptuous as vol
from datetime import timedelta

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICES, CONF_SENSORS,
    TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

AUTH_CODE = 'feixun.SH_1'
TOKEN_FILE = '.phicomm.token.'
USER_AGENT = 'zhilian/5.7.0 (iPhone; iOS 10.0.2; Scale/3.00)'

TOKEN_URL = 'https://accountsym.phicomm.com/v1/login'
DATA_URL = 'https://aircleaner.phicomm.com/aircleaner/getIndexData'

SENSOR_PM25 = 'pm25'
SENSOR_HCHO = 'hcho'
SENSOR_TEMPERATURE = 'temperature'
SENSOR_HUMIDITY = 'humidity'

DEFAULT_NAME = 'Phicomm'
DEFAULT_SENSORS = [SENSOR_PM25,SENSOR_HCHO, SENSOR_TEMPERATURE,SENSOR_HUMIDITY]

SENSOR_MAP = {
    SENSOR_PM25: ('PM2.5', 'μg/m³', 'blur'),
    SENSOR_HCHO: ('HCHO', 'mg/m³', 'biohazard'),
    SENSOR_TEMPERATURE: ('Temperature', TEMP_CELSIUS, 'thermometer'),
    SENSOR_HUMIDITY: ('Humidity', '%', 'water-percent')
}

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_DEVICES, default=1): cv.positive_int,
    vol.Optional(CONF_SENSORS, default=DEFAULT_SENSORS):
        vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_MAP)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Phicomm sensor."""
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    count = config.get(CONF_DEVICES)
    sensors = config[CONF_SENSORS]

    phicomm = PhicommData(username, password,
        hass.config.path(TOKEN_FILE + username), count * len(sensors))

    index = 0
    devices = []
    while index < count:
        for sensor_type in sensors:
            devices.append(PhicommSensor(phicomm, name, index, sensor_type))
        index += 1
    add_devices(devices, True)


class PhicommSensor(Entity):
    """Implementation of a Phicomm sensor."""

    def __init__(self, phicomm, name, index, sensor_type):
        """Initialize the Phicomm sensor."""
        sensor_name,unit,icon = SENSOR_MAP[sensor_type]
        if index:
            name += str(index + 1)
        self._name = name + ' ' + sensor_name
        self._index = index
        self._sensor_type = sensor_type
        self._unit = unit
        self._icon = 'mdi:' + icon
        self.phicomm = phicomm

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def available(self):
        """Return if the sensor data are available."""
        data = self.data
        return data and data.get('online') == '1'

    @property
    def state(self):
        """Return the state of the device."""
        data = self.data
        return data.get(self._sensor_type) if data else None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self.data if self._sensor_type == SENSOR_PM25 else None

    def update(self):
        """Get the latest data from Phicomm server and update the state."""
        _LOGGER.info("Begin update: %s", self.name)
        self.phicomm.update()

    @property
    def data(self):
        """Get data with current device index."""
        devs = self.phicomm.devs;
        if devs and self._index < len(devs):
            return devs[self._index].get('catDev')
        return None


class PhicommData():
    """Class for handling the data retrieval."""

    def __init__(self, username, password, token_path, update_cycle):
        """Initialize the data object."""
        self._username = username
        self._password = password
        self._token_path = token_path
        self._update_cycle = update_cycle
        self._update_times = 0
        self.devs = None

        try:
            with open(self._token_path) as f:
                self._token = f.read()
                _LOGGER.debug("Load: %s => %s", self._token_path, self._token)
        except:
            self._token = None

    def update(self):
        """Update and handle data from Phicomm server."""
        if self._update_times % self._update_cycle == 0:
            try:
                json = self.fetch()
                if ('error' in json) and (json['error'] != '0'):
                    _LOGGER.debug("Reset token: error=%s", json['error'])
                    self._token = None
                    json = self.fetch()
                self.devs = json['data']['devs']
                _LOGGER.info("Get data: devs=%s", self.devs)
            except:
                import traceback
                _LOGGER.error("Exception: %s", traceback.format_exc())

        self._update_times += 1

    def fetch(self):
        """Fetch the latest data from Phicomm server."""
        if self._token == None:
            import hashlib
            md5 = hashlib.md5()
            md5.update(self._password.encode('utf8'))
            data = {
                'authorizationcode': AUTH_CODE,
                'phonenumber': self._username,
                'password': md5.hexdigest().upper()
            }
            headers = {'User-Agent': USER_AGENT}
            json = requests.post(TOKEN_URL, headers=headers, data=data).json()
            _LOGGER.debug("Get token: %s", json)
            if 'access_token' in json:
                self._token = json['access_token']
                with open(self._token_path, 'w') as f:
                    f.write(self._token)
            else:
                return None
        headers = {'User-Agent': USER_AGENT, 'Authorization': self._token}
        return requests.get(DATA_URL, headers=headers).json()
