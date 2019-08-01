"""Counter for the days until an HTTPS (TLS) certificate will expire."""
import logging
import socket
import ssl
from datetime import datetime, timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, DEFAULT_NAME, DEFAULT_PORT

SCAN_INTERVAL = timedelta(hours=12)

TIMEOUT = 10.0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up certificate expiry sensor."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
    )
    return True


async def async_setup_entry(hass, entry, async_add_entities):
    """Add cert-expiry entry."""
    async_add_entities(
        [SSLCertificate(entry.title, entry.data[CONF_HOST], entry.data[CONF_PORT])],
        True,
    )
    return True


class SSLCertificate(Entity):
    """Implementation of the certificate expiry sensor."""

    def __init__(self, sensor_name, server_name, server_port):
        """Initialize the sensor."""
        self.server_name = server_name
        self.server_port = server_port
        self._name = sensor_name
        self._state = None
        self._available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "days"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:certificate"

    @property
    def available(self):
        """Icon to use in the frontend, if any."""
        return self._available

    def update(self):
        """Fetch the certificate information."""
        ctx = ssl.create_default_context()
        try:
            address = (self.server_name, self.server_port)
            with socket.create_connection(address, timeout=TIMEOUT) as sock:
                with ctx.wrap_socket(sock, server_hostname=address[0]) as ssock:
                    cert = ssock.getpeercert()

        except socket.gaierror:
            _LOGGER.error("Cannot resolve hostname: %s", self.server_name)
            self._available = False
            return
        except socket.timeout:
            _LOGGER.error("Connection timeout with server: %s", self.server_name)
            self._available = False
            return
        except OSError:
            _LOGGER.error(
                "Cannot fetch certificate from %s", self.server_name, exc_info=1
            )
            self._available = False
            return

        ts_seconds = ssl.cert_time_to_seconds(cert["notAfter"])
        timestamp = datetime.fromtimestamp(ts_seconds)
        expiry = timestamp - datetime.today()
        self._available = True
        self._state = expiry.days
