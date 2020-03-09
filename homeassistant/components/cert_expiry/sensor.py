"""Counter for the days until an HTTPS (TLS) certificate will expire."""
from datetime import datetime, timedelta
import logging
import socket
import ssl

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .helper import get_cert

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up certificate expiry sensor."""

    @callback
    def do_import(_):
        """Process YAML import after HA is fully started."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
            )
        )

    # Delay to avoid validation during setup in case we're checking our own cert.
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, do_import)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add cert-expiry entry."""
    async_add_entities(
        [SSLCertificate(entry.title, entry.data[CONF_HOST], entry.data[CONF_PORT])],
        False,
        # Don't update in case we're checking our own cert.
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
        self._valid = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return f"{self.server_name}:{self.server_port}"

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
        """Return the availability of the sensor."""
        return self._available

    async def async_added_to_hass(self):
        """Once the entity is added we should update to get the initial data loaded."""

        @callback
        def do_update(_):
            """Run the update method when the start event was fired."""
            self.async_schedule_update_ha_state(True)

        if self.hass.is_running:
            self.async_schedule_update_ha_state(True)
        else:
            # Delay until HA is fully started in case we're checking our own cert.
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, do_update)

    def update(self):
        """Fetch the certificate information."""
        try:
            cert = get_cert(self.server_name, self.server_port)
        except socket.gaierror:
            _LOGGER.error("Cannot resolve hostname: %s", self.server_name)
            self._available = False
            self._valid = False
            return
        except socket.timeout:
            _LOGGER.error("Connection timeout with server: %s", self.server_name)
            self._available = False
            self._valid = False
            return
        except (ssl.CertificateError, ssl.SSLError):
            self._available = True
            self._state = 0
            self._valid = False
            return

        ts_seconds = ssl.cert_time_to_seconds(cert["notAfter"])
        timestamp = datetime.fromtimestamp(ts_seconds)
        expiry = timestamp - datetime.today()
        self._available = True
        self._state = expiry.days
        self._valid = True

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        attr = {"is_valid": self._valid}

        return attr
