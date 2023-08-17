"""Counter for the days until an HTTPS (TLS) certificate will expire."""
from __future__ import annotations

from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CertExpiryDataUpdateCoordinator
from .const import DEFAULT_PORT, DOMAIN

SCAN_INTERVAL = timedelta(hours=12)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add cert-expiry entry."""
    coordinator: CertExpiryDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        SSLCertificateTimestamp(coordinator),
    ]

    async_add_entities(sensors, True)


class CertExpiryEntity(CoordinatorEntity[CertExpiryDataUpdateCoordinator]):
    """Defines a base Cert Expiry entity."""

    _attr_icon = "mdi:certificate"
    _attr_has_entity_name = True

    @property
    def extra_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "is_valid": self.coordinator.is_cert_valid,
            "error": str(self.coordinator.cert_error),
        }


class SSLCertificateTimestamp(CertExpiryEntity, SensorEntity):
    """Implementation of the Cert Expiry timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "certificate_expiry_timestamp"

    def __init__(
        self,
        coordinator: CertExpiryDataUpdateCoordinator,
    ) -> None:
        """Initialize a Cert Expiry timestamp sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.host}:{coordinator.port}-timestamp"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.host}:{coordinator.port}")},
            name=coordinator.name,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data
        return None
