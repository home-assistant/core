"""Counter for the days until an HTTPS (TLS) certificate will expire."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    TIME_DAYS,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

from .const import DEFAULT_PORT, DOMAIN
from .errors import TemporaryFailure, ValidationFailure
from .helper import get_cert_time_to_expiry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_NAME, invalidation_version="0.109"),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        }
    ),
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up certificate expiry sensor."""

    @callback
    def schedule_import(_):
        """Schedule delayed import after HA is fully started."""
        async_call_later(hass, 10, do_import)

    @callback
    def do_import(_):
        """Process YAML import."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
            )
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, schedule_import)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add cert-expiry entry."""
    days = 0
    error = None
    hostname = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{hostname}:{port}")

    try:
        days = await get_cert_time_to_expiry(hass, hostname, port)
    except TemporaryFailure as err:
        _LOGGER.error(err)
        raise PlatformNotReady
    except ValidationFailure as err:
        error = err

    async_add_entities(
        [SSLCertificate(hostname, port, days, error)], False,
    )
    return True


class SSLCertificate(Entity):
    """Implementation of the certificate expiry sensor."""

    def __init__(self, server_name, server_port, days, error):
        """Initialize the sensor."""
        self.server_name = server_name
        self.server_port = server_port
        display_port = f":{server_port}" if server_port != DEFAULT_PORT else ""
        self._name = f"Cert Expiry ({self.server_name}{display_port})"
        self._available = True
        self._error = error
        self._state = days
        self._valid = False
        if error is None:
            self._valid = True

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
        return TIME_DAYS

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

    async def async_update(self):
        """Fetch the certificate information."""
        try:
            days_to_expiry = await get_cert_time_to_expiry(
                self.hass, self.server_name, self.server_port
            )
        except TemporaryFailure as err:
            _LOGGER.error(err.args[0])
            self._available = False
            return
        except ValidationFailure as err:
            _LOGGER.error(
                "Certificate validation error: %s [%s]", self.server_name, err
            )
            self._available = True
            self._error = err
            self._state = 0
            self._valid = False
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error checking %s:%s", self.server_name, self.server_port
            )
            self._available = False
            return

        self._available = True
        self._error = None
        self._state = days_to_expiry
        self._valid = True

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {"is_valid": self._valid, "error": str(self._error)}
