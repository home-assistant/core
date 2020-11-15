"""Counter for the days until an HTTPS (TLS) certificate will expire."""
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    DEVICE_CLASS_TIMESTAMP,
    EVENT_HOMEASSISTANT_START,
    TIME_DAYS,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt

from .const import DEFAULT_PORT, DOMAIN

SCAN_INTERVAL = timedelta(hours=12)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
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
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        SSLCertificateDays(coordinator),
        SSLCertificateTimestamp(coordinator),
    ]

    async_add_entities(sensors, True)


class CertExpiryEntity(CoordinatorEntity):
    """Defines a base Cert Expiry entity."""

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:certificate"

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "is_valid": self.coordinator.is_cert_valid,
            "error": str(self.coordinator.cert_error),
        }


class SSLCertificateDays(CertExpiryEntity):
    """Implementation of the Cert Expiry days sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Cert Expiry ({self.coordinator.name})"

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.coordinator.is_cert_valid:
            return 0

        expiry = self.coordinator.data - dt.utcnow()
        return expiry.days

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return f"{self.coordinator.host}:{self.coordinator.port}"

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return TIME_DAYS


class SSLCertificateTimestamp(CertExpiryEntity):
    """Implementation of the Cert Expiry timestamp sensor."""

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Cert Expiry Timestamp ({self.coordinator.name})"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.isoformat()
        return None

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return f"{self.coordinator.host}:{self.coordinator.port}-timestamp"
