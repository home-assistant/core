"""Counter for the days until an HTTPS (TLS) certificate will expire."""
import logging
import socket
import ssl
from datetime import datetime, timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_PORT,
                                 EVENT_HOMEASSISTANT_START)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'SSL Certificate Expiry'
DEFAULT_PORT = 443

SCAN_INTERVAL = timedelta(hours=12)

TIMEOUT = 10.0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up certificate expiry sensor."""
    def run_setup(event):
        """Wait until Home Assistant is fully initialized before creating.

        Delay the setup until Home Assistant is fully initialized.
        """
        server_name = config.get(CONF_HOST)
        server_port = config.get(CONF_PORT)
        sensor_name = config.get(CONF_NAME)

        add_entities([SSLCertificate(sensor_name, server_name, server_port)],
                     True)

    # To allow checking of the HA certificate we must first be running.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, run_setup)


class SSLCertificate(Entity):
    """Implementation of the certificate expiry sensor."""

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
        """Fetch the certificate information."""
        try:
            ctx = ssl.create_default_context()
            host_info = socket.getaddrinfo(self.server_name, self.server_port)
            family = host_info[0][0]
            sock = ctx.wrap_socket(
                socket.socket(family=family), server_hostname=self.server_name)
            sock.settimeout(TIMEOUT)
            sock.connect((self.server_name, self.server_port))
        except socket.gaierror:
            _LOGGER.error("Cannot resolve hostname: %s", self.server_name)
            return
        except socket.timeout:
            _LOGGER.error(
                "Connection timeout with server: %s", self.server_name)
            return
        except OSError:
            _LOGGER.error("Cannot connect to %s", self.server_name)
            return

        try:
            cert = sock.getpeercert()
        except OSError:
            _LOGGER.error("Cannot fetch certificate from %s", self.server_name)
            return

        ts_seconds = ssl.cert_time_to_seconds(cert['notAfter'])
        timestamp = datetime.fromtimestamp(ts_seconds)
        expiry = timestamp - datetime.today()
        self._state = expiry.days
