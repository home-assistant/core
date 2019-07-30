"""Support for retrieving status info from Google Wifi/OnHub routers."""
import logging
from datetime import timedelta

import voluptuous as vol
import requests

from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_MONITORED_CONDITIONS, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_VERSION = 'current_version'
ATTR_LAST_RESTART = 'last_restart'
ATTR_LOCAL_IP = 'local_ip'
ATTR_NEW_VERSION = 'new_version'
ATTR_STATUS = 'status'
ATTR_UPTIME = 'uptime'

DEFAULT_HOST = 'testwifi.here'
DEFAULT_NAME = 'google_wifi'

ENDPOINT = '/api/v1/status'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)

MONITORED_CONDITIONS = {
    ATTR_CURRENT_VERSION: [
        ['software', 'softwareVersion'],
        None,
        'mdi:checkbox-marked-circle-outline'
    ],
    ATTR_NEW_VERSION: [
        ['software', 'updateNewVersion'],
        None,
        'mdi:update'
    ],
    ATTR_UPTIME: [
        ['system', 'uptime'],
        'days',
        'mdi:timelapse'
    ],
    ATTR_LAST_RESTART: [
        ['system', 'uptime'],
        None,
        'mdi:restart'
    ],
    ATTR_LOCAL_IP: [
        ['wan', 'localIpAddress'],
        None,
        'mdi:access-point-network'
    ],
    ATTR_STATUS: [
        ['wan', 'online'],
        None,
        'mdi:google'
    ]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=list(MONITORED_CONDITIONS)):
    vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Google Wifi sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    conditions = config.get(CONF_MONITORED_CONDITIONS)

    api = GoogleWifiAPI(host, conditions)
    dev = []
    for condition in conditions:
        dev.append(GoogleWifiSensor(api, name, condition))

    add_entities(dev, True)


class GoogleWifiSensor(Entity):
    """Representation of a Google Wifi sensor."""

    def __init__(self, api, name, variable):
        """Initialize a Google Wifi sensor."""
        self._api = api
        self._name = name
        self._state = None

        variable_info = MONITORED_CONDITIONS[variable]
        self._var_name = variable
        self._var_units = variable_info[1]
        self._var_icon = variable_info[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{}_{}'.format(self._name, self._var_name)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._var_icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._var_units

    @property
    def available(self):
        """Return availability of Google Wifi API."""
        return self._api.available

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data from the Google Wifi API."""
        self._api.update()
        if self.available:
            self._state = self._api.data[self._var_name]
        else:
            self._state = None


class GoogleWifiAPI:
    """Get the latest data and update the states."""

    def __init__(self, host, conditions):
        """Initialize the data object."""
        uri = 'http://'
        resource = "{}{}{}".format(uri, host, ENDPOINT)
        self._request = requests.Request('GET', resource).prepare()
        self.raw_data = None
        self.conditions = conditions
        self.data = {
            ATTR_CURRENT_VERSION: STATE_UNKNOWN,
            ATTR_NEW_VERSION: STATE_UNKNOWN,
            ATTR_UPTIME: STATE_UNKNOWN,
            ATTR_LAST_RESTART: STATE_UNKNOWN,
            ATTR_LOCAL_IP: STATE_UNKNOWN,
            ATTR_STATUS: STATE_UNKNOWN
        }
        self.available = True
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the router."""
        try:
            with requests.Session() as sess:
                response = sess.send(self._request, timeout=10)
            self.raw_data = response.json()
            self.data_format()
            self.available = True
        except (ValueError, requests.exceptions.ConnectionError):
            _LOGGER.warning("Unable to fetch data from Google Wifi")
            self.available = False
            self.raw_data = None

    def data_format(self):
        """Format raw data into easily accessible dict."""
        for attr_key in self.conditions:
            value = MONITORED_CONDITIONS[attr_key]
            try:
                primary_key = value[0][0]
                sensor_key = value[0][1]
                if primary_key in self.raw_data:
                    sensor_value = self.raw_data[primary_key][sensor_key]
                    # Format sensor for better readability
                    if (attr_key == ATTR_NEW_VERSION and
                            sensor_value == '0.0.0.0'):
                        sensor_value = 'Latest'
                    elif attr_key == ATTR_UPTIME:
                        sensor_value = round(sensor_value / (3600 * 24), 2)
                    elif attr_key == ATTR_LAST_RESTART:
                        last_restart = (
                            dt.now() - timedelta(seconds=sensor_value))
                        sensor_value = last_restart.strftime(
                            '%Y-%m-%d %H:%M:%S')
                    elif attr_key == ATTR_STATUS:
                        if sensor_value:
                            sensor_value = 'Online'
                        else:
                            sensor_value = 'Offline'
                    elif attr_key == ATTR_LOCAL_IP:
                        if not self.raw_data['wan']['online']:
                            sensor_value = STATE_UNKNOWN

                    self.data[attr_key] = sensor_value
            except KeyError:
                _LOGGER.error("Router does not support %s field. "
                              "Please remove %s from monitored_conditions",
                              sensor_key, attr_key)
                self.data[attr_key] = STATE_UNKNOWN
