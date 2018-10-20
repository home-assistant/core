"""
Tracks the latency of a host by sending ICMP echo requests (ping).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ping/
"""
import logging
import subprocess
import re
import sys
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_NAME, CONF_HOST

_LOGGER = logging.getLogger(__name__)

ATTR_ROUND_TRIP_TIME_AVG = 'round_trip_time_avg'
ATTR_ROUND_TRIP_TIME_MAX = 'round_trip_time_max'
ATTR_ROUND_TRIP_TIME_MDEV = 'round_trip_time_mdev'
ATTR_ROUND_TRIP_TIME_MIN = 'round_trip_time_min'

CONF_PING_COUNT = 'count'

DEFAULT_NAME = 'Ping Binary sensor'
DEFAULT_PING_COUNT = 5
DEFAULT_DEVICE_CLASS = 'connectivity'

SCAN_INTERVAL = timedelta(minutes=5)

PING_MATCHER = re.compile(
    r'(?P<min>\d+.\d+)\/(?P<avg>\d+.\d+)\/(?P<max>\d+.\d+)\/(?P<mdev>\d+.\d+)')

PING_MATCHER_BUSYBOX = re.compile(
    r'(?P<min>\d+.\d+)\/(?P<avg>\d+.\d+)\/(?P<max>\d+.\d+)')

WIN32_PING_MATCHER = re.compile(
    r'(?P<min>\d+)ms.+(?P<max>\d+)ms.+(?P<avg>\d+)ms')

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PING_COUNT, default=DEFAULT_PING_COUNT): cv.positive_int,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ping Binary sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    count = config.get(CONF_PING_COUNT)

    add_entities([PingBinarySensor(name, PingData(host, count))], True)


class PingBinarySensor(BinarySensorDevice):
    """Representation of a Ping Binary sensor."""

    def __init__(self, name, ping):
        """Initialize the Ping Binary sensor."""
        self._name = name
        self.ping = ping

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEFAULT_DEVICE_CLASS

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.ping.available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the ICMP checo request."""
        if self.ping.data is not False:
            return {
                ATTR_ROUND_TRIP_TIME_AVG: self.ping.data['avg'],
                ATTR_ROUND_TRIP_TIME_MAX: self.ping.data['max'],
                ATTR_ROUND_TRIP_TIME_MDEV: self.ping.data['mdev'],
                ATTR_ROUND_TRIP_TIME_MIN: self.ping.data['min'],
            }

    def update(self):
        """Get the latest data."""
        self.ping.update()


class PingData:
    """The Class for handling the data retrieval."""

    def __init__(self, host, count):
        """Initialize the data object."""
        self._ip_address = host
        self._count = count
        self.data = {}
        self.available = False

        if sys.platform == 'win32':
            self._ping_cmd = [
                'ping', '-n', str(self._count), '-w', '1000', self._ip_address]
        else:
            self._ping_cmd = [
                'ping', '-n', '-q', '-c', str(self._count), '-W1',
                self._ip_address]

    def ping(self):
        """Send ICMP echo request and return details if success."""
        pinger = subprocess.Popen(
            self._ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out = pinger.communicate()
            _LOGGER.debug("Output is %s", str(out))
            if sys.platform == 'win32':
                match = WIN32_PING_MATCHER.search(str(out).split('\n')[-1])
                rtt_min, rtt_avg, rtt_max = match.groups()
                return {
                    'min': rtt_min,
                    'avg': rtt_avg,
                    'max': rtt_max,
                    'mdev': ''}
            if 'max/' not in str(out):
                match = PING_MATCHER_BUSYBOX.search(str(out).split('\n')[-1])
                rtt_min, rtt_avg, rtt_max = match.groups()
                return {
                    'min': rtt_min,
                    'avg': rtt_avg,
                    'max': rtt_max,
                    'mdev': ''}
            match = PING_MATCHER.search(str(out).split('\n')[-1])
            rtt_min, rtt_avg, rtt_max, rtt_mdev = match.groups()
            return {
                'min': rtt_min,
                'avg': rtt_avg,
                'max': rtt_max,
                'mdev': rtt_mdev}
        except (subprocess.CalledProcessError, AttributeError):
            return False

    def update(self):
        """Retrieve the latest details from the host."""
        self.data = self.ping()
        self.available = bool(self.data)
