"""Counts the days an HTTPS (TLS) certificate will expire (days).

For more details about this sensor please refer to the
documentation at https://home-assistant.io/components/sensor.cert_expiry
"""
import logging
import ssl
import socket
import datetime
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_PORT)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'SSL Certificate Expiry'
DEFAULT_PORT = 443

SCAN_INTERVAL = datetime.timedelta(hours=12)
TIMEOUT = 10.0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup certificate expiry sensor."""
    server_name = config.get(CONF_HOST)
    server_port = config.get(CONF_PORT)
    sensor_name = config.get(CONF_NAME)
    add_devices([SSLCertificate(sensor_name, server_name, server_port)])


class SSLCertificate(Entity):
    """Implements certificate expiry sensor."""

    def __init__(self, sensor_name, server_name, server_port):
        """Initialize the sensor."""
        self.server_name = server_name
        self.server_port = server_port
        self._name = sensor_name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return 'days'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:certificate'

    def update(self):
        """Fetch certificate information."""
        try:
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(socket.socket(),
                                   server_hostname=self.server_name)
            sock.settimeout(TIMEOUT)
            sock.connect((self.server_name, self.server_port))
        except socket.gaierror:
            _LOGGER.error('Cannot resolve name %s', self.server_name)
        except socket.timeout:
            _LOGGER.error('Connection timeout with server %s',
                          self.server_name)
        except OSError as excp:
            _LOGGER.error('Cannot connect to %s', self.server_name)
            raise excp

        try:
            cert = sock.getpeercert()
        except OSError as excp:
            _LOGGER.error('Cannot fetch certificate from %s',
                          (self.server_name))
            raise excp

        ts_seconds = ssl.cert_time_to_seconds(cert['notAfter'])
        timestamp = datetime.datetime.fromtimestamp(ts_seconds)
        expiry = timestamp - datetime.datetime.today()
        self._state = expiry.days
