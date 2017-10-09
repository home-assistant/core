"""
Support gathering system information of hosts which are running netdata.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.netdata/
"""
import logging
from datetime import timedelta
from urllib.parse import urlsplit

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_NAME, CONF_RESOURCES)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'api/v1'
_REALTIME = 'before=0&after=-1&options=seconds'

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'Netdata'
DEFAULT_PORT = '19999'

SCAN_INTERVAL = timedelta(minutes=1)

SENSOR_TYPES = {
    'memory_free': ['RAM Free', 'MiB', 'system.ram', 'free', 1],
    'memory_used': ['RAM Used', 'MiB', 'system.ram', 'used', 1],
    'memory_cached': ['RAM Cached', 'MiB', 'system.ram', 'cached', 1],
    'memory_buffers': ['RAM Buffers', 'MiB', 'system.ram', 'buffers', 1],
    'swap_free': ['Swap Free', 'MiB', 'system.swap', 'free', 1],
    'swap_used': ['Swap Used', 'MiB', 'system.swap', 'used', 1],
    'processes_running': ['Processes Running', 'Count', 'system.processes',
                          'running', 0],
    'processes_blocked': ['Processes Blocked', 'Count', 'system.processes',
                          'blocked', 0],
    'system_load': ['System Load', '15 min', 'system.load', 'load15', 2],
    'system_io_in': ['System IO In', 'Count', 'system.io', 'in', 0],
    'system_io_out': ['System IO Out', 'Count', 'system.io', 'out', 0],
    'ipv4_in': ['IPv4 In', 'kb/s', 'system.ipv4', 'received', 0],
    'ipv4_out': ['IPv4 Out', 'kb/s', 'system.ipv4', 'sent', 0],
    'disk_free': ['Disk Free', 'GiB', 'disk_space._', 'avail', 2],
    'cpu_iowait': ['CPU IOWait', '%', 'system.cpu', 'iowait', 1],
    'cpu_user': ['CPU User', '%', 'system.cpu', 'user', 1],
    'cpu_system': ['CPU System', '%', 'system.cpu', 'system', 1],
    'cpu_softirq': ['CPU SoftIRQ', '%', 'system.cpu', 'softirq', 1],
    'cpu_guest': ['CPU Guest', '%', 'system.cpu', 'guest', 1],
    'uptime': ['Uptime', 's', 'system.uptime', 'uptime', 0],
    'packets_received': ['Packets Received', 'packets/s', 'ipv4.packets',
                         'received', 0],
    'packets_sent': ['Packets Sent', 'packets/s', 'ipv4.packets',
                     'sent', 0],
    'connections': ['Active Connections', 'Count',
                    'netfilter.conntrack_sockets', 'connections', 0]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_RESOURCES, default=['memory_free']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Netdata sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    url = 'http://{}:{}'.format(host, port)
    data_url = '{}/{}/data?chart='.format(url, _RESOURCE)
    resources = config.get(CONF_RESOURCES)

    values = {}
    for key, value in sorted(SENSOR_TYPES.items()):
        if key in resources:
            values.setdefault(value[2], []).append(key)

    dev = []
    for chart in values:
        rest_url = '{}{}&{}'.format(data_url, chart, _REALTIME)
        rest = NetdataData(rest_url)
        rest.update()
        for sensor_type in values[chart]:
            dev.append(NetdataSensor(rest, name, sensor_type))

    add_devices(dev, True)


class NetdataSensor(Entity):
    """Implementation of a Netdata sensor."""

    def __init__(self, rest, name, sensor_type):
        """Initialize the Netdata sensor."""
        self.rest = rest
        self.type = sensor_type
        self._name = '{} {}'.format(name, SENSOR_TYPES[self.type][0])
        self._precision = SENSOR_TYPES[self.type][4]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the resources."""
        value = self.rest.data

        if value is not None:
            netdata_id = SENSOR_TYPES[self.type][3]
            if netdata_id in value:
                return "{0:.{1}f}".format(value[netdata_id], self._precision)
        return None

    @property
    def available(self):
        """Could the resource be accessed during the last update call."""
        return self.rest.available

    def update(self):
        """Get the latest data from Netdata REST API."""
        self.rest.update()


class NetdataData(object):
    """The class for handling the data retrieval."""

    def __init__(self, resource):
        """Initialize the data object."""
        self._resource = resource
        self.data = None
        self.available = True

    def update(self):
        """Get the latest data from the Netdata REST API."""
        try:
            response = requests.get(self._resource, timeout=5)
            det = response.json()
            self.data = {k: v for k, v in zip(det['labels'], det['data'][0])}
            self.available = True
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Connection error: %s", urlsplit(self._resource)[1])
            self.data = None
            self.available = False
