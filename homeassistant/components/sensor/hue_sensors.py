"""
Sensor for checking the status of Hue sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hue_sensors/
"""
import json
import logging
from datetime import timedelta

import requests

from homeassistant.const import (CONF_FILENAME)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
PHUE_CONFIG_FILE = 'phue.conf'
SCAN_INTERVAL = timedelta(seconds=1)
TAP_BUTTON_NAMES = {34: '1_click', 16: '2_click', 17: '3_click', 18: '4_click'}


def load_conf(filepath):
    """Return the URL for API requests."""
    with open(filepath, 'r') as file_path:
        data = json.load(file_path)
        ip_add = next(data.keys().__iter__())
        username = data[ip_add]['username']
        url = 'http://' + ip_add + '/api/' + username + '/sensors'
    return url


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tube sensor."""
    filename = config.get(CONF_FILENAME, PHUE_CONFIG_FILE)  # returns the IP
    filepath = hass.config.path(filename)
    url = load_conf(filepath)
    data = HueSensorData(url)
    data.update()
    sensors = []
    for key in data.data.keys():
        sensors.append(HueSensor(key, data))
    add_devices(sensors, True)


class HueSensorData(object):
    """Get the latest sensor data."""

    def __init__(self, url):
        """Initialize the data object."""
        self.url = url
        self.data = None

    # Update only once in scan interval.
    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data."""
        response = requests.get(self.url)
        if response.status_code != 200:
            _LOGGER.warning("Invalid response from API")
        else:
            self.data = parse_hue_api_response(response.json())


class HueSensor(Entity):
    """Class to hold Hue Sensor basic info."""

    ICON = 'mdi:run-fast'

    def __init__(self, hue_id, data):
        """Initialize the sensor object."""
        self._hue_id = hue_id
        self._data = data    # data is in .data
        self._name = self._data.data[self._hue_id]['name']
        self._model = self._data.data[self._hue_id]['model']
        self._state = self._data.data[self._hue_id]['state']
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def device_state_attributes(self):
        """Only motion sensors have attributes currently, but could extend."""
        return self._attributes

    def update(self):
        """Update the sensor."""
        self._data.update()
        self._state = self._data.data[self._hue_id]['state']
        if self._model == 'SML001':
            self._attributes['light_level'] = self._data.data[
                self._hue_id]['light_level']
            self._attributes['temperature'] = self._data.data[
                self._hue_id]['temperature']
        elif self._model in ['RWL021', 'ZGPSWITCH']:
            self.ICON = 'mdi:remote'
            self._attributes['last updated'] = self._data.data[
                self._hue_id]['last_updated']
        elif self._model == 'Geofence':
            self.ICON = 'mdi:cellphone'


def parse_hue_api_response(response):
    """Take in the Hue API json response."""
    data_dict = {}    # The list of sensors, referenced by their hue_id.

    # Loop over all keys (1,2 etc) to identify sensors and get data.
    for key in response.keys():
        sensor = response[key]

        if sensor['modelid'] in ['RWL021', 'SML001', 'ZGPSWITCH']:
            _key = sensor['uniqueid'].split(':')[-1][0:5]

            if sensor['modelid'] == 'RWL021':
                data_dict[_key] = parse_rwl(sensor)
            elif sensor['modelid'] == 'ZGPSWITCH':
                data_dict[_key] = parse_zpg(sensor)
            else:
                if _key not in data_dict.keys():
                    data_dict[_key] = parse_sml(sensor)
                else:
                    data_dict[_key].update(parse_sml(sensor))

        elif sensor['modelid'] == 'HA_GEOFENCE':
            data_dict['Geofence'] = parse_geofence(sensor)
    return data_dict


def parse_sml(response):
    """Parse the json for a SML001 Hue motion sensor and return the data."""
    if 'ambient light' in response['name']:
        data = {'light_level': response['state']['lightlevel']}

    elif 'temperature' in response['name']:
        data = {'temperature': response['state']['temperature']/100.0}

    else:
        name_raw = response['name']
        arr = name_raw.split()
        arr.insert(-1, 'motion')
        name = ' '.join(arr)
        hue_state = response['state']['presence']
        if hue_state is True:
            state = 'on'
        else:
            state = 'off'

        data = {'model': response['modelid'],
                'state': state,
                'name': name}
    return data


def parse_zpg(response):
    """Parse the json response for a ZGPSWITCH Hue Tap."""
    press = response['state']['buttonevent']

    button = TAP_BUTTON_NAMES[press]

    data = {'model': 'ZGPSWITCH',
            'name': response['name'],
            'state': button,
            'last_updated': response['state']['lastupdated'].split('T')}
    return data


def parse_rwl(response):
    """Parse the json response for a RWL021 Hue remote."""
    press = str(response['state']['buttonevent'])

    if press[-1] in ['0', '2']:
        button = str(press)[0] + '_click'
    else:
        button = str(press)[0] + '_hold'

    data = {'model': 'RWL021',
            'name': response['name'],
            'state': button,
            'last_updated': response['state']['lastupdated'].split('T')}
    return data


def parse_geofence(response):
    """Parse the json response for a GEOFENCE and return the data."""
    hue_state = response['state']['presence']
    if hue_state is True:
        state = 'on'
    else:
        state = 'off'
    data = {'name': response['name'],
            'model': 'Geofence',
            'state': state}
    return data
