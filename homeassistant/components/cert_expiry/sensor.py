"""Counter for the days until an HTTPS (TLS) certificate will expire."""
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    DEVICE_CLASS_TIMESTAMP,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
        SSLCertificateTimestamp(coordinator),
    ]

    async_add_entities(sensors, True)


class CertExpiryEntity(CoordinatorEntity):
    """Defines a base Cert Expiry entity."""

    _attr_icon = "mdi:certificate"

    @property
    def extra_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "is_valid": self.coordinator.is_cert_valid,
            "error": str(self.coordinator.cert_error),
        }


class SSLCertificateTimestamp(CertExpiryEntity, SensorEntity):
    """Implementation of the Cert Expiry timestamp sensor."""

    _attr_device_class = DEVICE_CLASS_TIMESTAMP

    def __init__(self, coordinator) -> None:
        """Initialize a Cert Expiry timestamp sensor."""
        super().__init__(coordinator)
        self._attr_name = f"Cert Expiry Timestamp ({coordinator.name})"
        self._attr_unique_id = f"{coordinator.host}:{coordinator.port}-timestamp"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.isoformat()
        return None
