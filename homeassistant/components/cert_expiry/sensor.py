"""Counter for the days until an HTTPS (TLS) certificate will expire."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import CertExpiryConfigEntry, CertExpiryDataUpdateCoordinator
from .entity import CertExpiryEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CertExpiryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add cert-expiry entry."""
    coordinator = entry.runtime_data

    sensors = [SSLCertificateTimestamp(coordinator)]

    async_add_entities(sensors, True)


class SSLCertificateTimestamp(CertExpiryEntity, SensorEntity):
    """Implementation of the Cert Expiry timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "certificate_expiry"

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
