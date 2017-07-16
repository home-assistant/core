"""
Support for retreiving status info from Google Wifi/OnHub routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.google_wifi/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import requests

import homeassistant.util.dt as dt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.util import Throttle
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_MONITORED_CONDITIONS,
    STATE_UNKNOWN)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)

_LOGGER = logging.getLogger(__name__)

ENDPOINT = '/api/v1/status'

ATTR_CURRENT_VERSION = 'current_version'
ATTR_NEW_VERSION = 'new_version'
ATTR_UPTIME = 'uptime'
ATTR_LAST_RESTART = 'last_restart'
ATTR_LOCAL_IP = 'local_ip'
ATTR_STATUS = 'status'

DEFAULT_NAME = 'google_wifi'
DEFAULT_HOST = 'testwifi.here'

MONITORED_CONDITIONS = {
    ATTR_CURRENT_VERSION: [
        'Current Version',
        None,
        'mdi:checkbox-marked-circle-outline'
    ],
    ATTR_NEW_VERSION: [
        'New Version',
        None,
        'mdi:update'
    ],
    ATTR_UPTIME: [
        'Uptime',
        'days',
        'mdi:timelapse'
    ],
    ATTR_LAST_RESTART: [
        'Last Network Restart',
        None,
        'mdi:restart'
    ],
    ATTR_LOCAL_IP: [
        'Local IP Address',
        None,
        'mdi:access-point-network'
    ],
    ATTR_STATUS: [
        'Status',
        None,
        'mdi:google'
    ]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Google Wifi sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    api = GoogleWifiAPI(host)

    sensors = [GoogleWifiSensor(hass, api, name, condition)
               for condition in config[CONF_MONITORED_CONDITIONS]]

    add_devices(sensors, True)


class GoogleWifiSensor(Entity):
    """Representation of a Google Wifi sensor."""

    def __init__(self, hass, api, name, variable):
        """Initialize a Pi-Hole sensor."""
        self._hass = hass
        self._api = api
        self._name = name
        self._state = STATE_UNKNOWN

        variable_info = MONITORED_CONDITIONS[variable]
        self._var_name = variable
        self._var_units = variable_info[1]
        self._var_icon = variable_info[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{}_{}".format(self._name, self._var_name)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._var_icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._var_units

    @property
    def availiable(self):
        """Return availiability of goole wifi api."""
        return self._api.availiable

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data from the Google Wifi API."""
        self._api.update()
        if self.availiable:
            self._state = self._api.data[self._var_name]
        else:
            self._state = STATE_UNKNOWN


class GoogleWifiAPI(object):
    """Get the latest data and update the states."""

    def __init__(self, host):
        """Initialize the data object."""
        uri = 'http://'
        resource = "{}{}{}".format(uri, host, ENDPOINT)

        self._request = requests.Request('GET', resource).prepare()
        self.raw_data = None
        self.data = {
            ATTR_CURRENT_VERSION: STATE_UNKNOWN,
            ATTR_NEW_VERSION: STATE_UNKNOWN,
            ATTR_UPTIME: STATE_UNKNOWN,
            ATTR_LAST_RESTART: STATE_UNKNOWN,
            ATTR_LOCAL_IP: STATE_UNKNOWN,
            ATTR_STATUS: STATE_UNKNOWN
        }
        self.availiable = True
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the router."""
        try:
            _LOGGER.error("Before request")
            with requests.Session() as sess:
                response = sess.send(
                    self._request, timeout=10)
            self.raw_data = response.json()
            _LOGGER.error(self.raw_data)
            self.data_format()
            self.availiable = True
        except ValueError:
            _LOGGER.error("Unable to fetch data from Google Wifi")
            self.availiable = False
            self.raw_data = None

    def data_format(self):
        """Format raw data into easily accessible dict."""
        for key, value in self.raw_data.items():
            if key == 'software':
                self.data[ATTR_CURRENT_VERSION] = value['softwareVersion']
                if value['updateNewVersion'] == '0.0.0.0':
                    self.data[ATTR_NEW_VERSION] = 'Latest'
                else:
                    self.data[ATTR_NEW_VERSION] = value['updateNewVersion']
            elif key == 'system':
                self.data[ATTR_UPTIME] = value['uptime'] / (3600 * 24)
                last_restart = dt.now() - timedelta(seconds=value['uptime'])
                self.data[ATTR_LAST_RESTART] = \
                    last_restart.strftime("%Y-%m-%d %H:%M:%S")
            elif key == 'wan':
                if value['online']:
                    self.data[ATTR_STATUS] = 'Online'
                else:
                    self.data[ATTR_STATUS] = 'Offline'
                if not value['ipAddress']:
                    self.data[ATTR_LOCAL_IP] = STATE_UNKNOWN
                else:
                    self.data[ATTR_LOCAL_IP] = value['localIpAddress']
