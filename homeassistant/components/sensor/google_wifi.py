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
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_MONITORED_CONDITIONS,
    STATE_UNKNOWN)

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
    ATTR_CURRENT_VERSION: ['Current Version',
                           None, 'mdi:network-question',
                           ['software', 'softwareVersion']],
    ATTR_NEW_VERSION: ['New Version',
                       None, 'mdi:update',
                       ['software', 'updateNewVersion']],
    ATTR_UPTIME: ['Uptime',
                  'days', 'mdi:timelapse',
                  ['system', 'uptime']],
    ATTR_LAST_RESTART: ['Last Network Restart',
                        None, 'mdi:restart',
                        None],
    ATTR_LOCAL_IP: ['Local IP Address',
                    None, 'mdi:access-point-network',
                    ['wan', 'localIpAddress']],
    ATTR_STATUS: ['Status',
                  None, 'mdi:google',
                  ['wan', 'online']]
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

        variable_info = MONITORED_CONDITIONS[variable]
        self._var_name = variable
        self._var_units = variable_info[1]
        self._var_icon = variable_info[2]
        self._var_key = variable_info[3]
        self._uptime_keys = MONITORED_CONDITIONS[ATTR_UPTIME][3]

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
        if self._var_name == ATTR_LAST_RESTART and self.availiable:
            uptime = self._api.data[self._uptime_keys[0]][self._uptime_keys[1]]
            last_restart = dt.now() - timedelta(seconds=uptime)
            return last_restart.strftime("%Y-%m-%d %H:%M:%S")

        if self.availiable:
            if (not self._api.data['wan']['ipAddress'] and
                    self._var_name == ATTR_LOCAL_IP):
                state_data = STATE_UNKNOWN
            else:
                state_data = self._api.data[self._var_key[0]][self._var_key[1]]

            if self._var_name == ATTR_UPTIME:
                return round(state_data / (24 * 3600), 2)
            elif self._var_name == ATTR_STATUS:
                if state_data:
                    return "Online"
                return "Offline"
            elif self._var_name == ATTR_NEW_VERSION:
                if state_data == '0.0.0.0':
                    return "Latest"
            return state_data

        return STATE_UNKNOWN

    def update(self):
        """Get the latest data from the Google Wifi API."""
        self._api.update()


class GoogleWifiAPI(object):
    """Get the latest data and update the states."""

    def __init__(self, host):
        """Initialize the data object."""
        uri = 'http://'
        resource = "{}{}{}".format(uri, host, ENDPOINT)

        self._request = requests.Request('GET', resource).prepare()
        self.data = None
        self.availiable = True
        self.update()

    def update(self):
        """Get the latest data from the router."""
        try:
            with requests.Session() as sess:
                response = sess.send(
                    self._request, timeout=10)
            self.data = response.json()
            self.availiable = True
        except ValueError:
            _LOGGER.error("Unable to fetch data from Google Wifi")
            self.availiable = False
            self.data = None
