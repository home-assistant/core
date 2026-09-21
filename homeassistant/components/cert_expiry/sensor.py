"""Sensors for the cert_expiry integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    CertExpiryConfigEntry,
    CertExpiryData,
    CertExpiryDataUpdateCoordinator,
)
from .entity import CertExpiryEntity

PARALLEL_UPDATES = 0

CERTIFICATE_VERSIONS = ["v1", "v3"]
TLS_VERSIONS: dict[str | None, str] = {
    "TLSv1": "tls_1_0",
    "TLSv1.1": "tls_1_1",
    "TLSv1.2": "tls_1_2",
    "TLSv1.3": "tls_1_3",
}


@dataclass(frozen=True, kw_only=True)
class CertExpirySensorEntityDescription(SensorEntityDescription):
    """Describes a Cert Expiry sensor entity."""

    value_fn: Callable[[CertExpiryData], StateType | datetime]


TIMESTAMP_DESCRIPTION = CertExpirySensorEntityDescription(
    key="timestamp",
    translation_key="certificate_expiry",
    device_class=SensorDeviceClass.TIMESTAMP,
    value_fn=lambda data: data.expires_at,
)

DIAGNOSTIC_DESCRIPTIONS: tuple[CertExpirySensorEntityDescription, ...] = (
    CertExpirySensorEntityDescription(
        key="serial_number",
        translation_key="serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.certificate.serial_number,
    ),
    CertExpirySensorEntityDescription(
        key="certificate_version",
        translation_key="certificate_version",
        device_class=SensorDeviceClass.ENUM,
        options=CERTIFICATE_VERSIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.certificate.version,
    ),
    CertExpirySensorEntityDescription(
        key="fingerprint",
        translation_key="fingerprint",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.certificate.fingerprint,
    ),
    CertExpirySensorEntityDescription(
        key="common_name",
        translation_key="common_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.certificate.common_name,
    ),
    CertExpirySensorEntityDescription(
        key="organization",
        translation_key="organization",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.certificate.organization,
    ),
    CertExpirySensorEntityDescription(
        key="organizational_unit",
        translation_key="organizational_unit",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.certificate.organizational_unit,
    ),
    CertExpirySensorEntityDescription(
        key="issuer_common_name",
        translation_key="issuer_common_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.certificate.issuer_common_name,
    ),
    CertExpirySensorEntityDescription(
        key="issuer_organization",
        translation_key="issuer_organization",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.certificate.issuer_organization,
    ),
    CertExpirySensorEntityDescription(
        key="tls_version",
        translation_key="tls_version",
        device_class=SensorDeviceClass.ENUM,
        options=list(TLS_VERSIONS.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: TLS_VERSIONS.get(data.tls_version),
    ),
    CertExpirySensorEntityDescription(
        key="cipher_suite",
        translation_key="cipher_suite",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.cipher_name,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CertExpiryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add cert-expiry entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            SSLCertificateTimestamp(coordinator, TIMESTAMP_DESCRIPTION),
            *(
                CertExpirySensor(coordinator, description)
                for description in DIAGNOSTIC_DESCRIPTIONS
            ),
        ]
    )


class CertExpirySensor(CertExpiryEntity, SensorEntity):
    """A sensor reading one value from the Cert Expiry data."""

    entity_description: CertExpirySensorEntityDescription

    def __init__(
        self,
        coordinator: CertExpiryDataUpdateCoordinator,
        description: CertExpirySensorEntityDescription,
    ) -> None:
        """Initialize a Cert Expiry sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class SSLCertificateTimestamp(CertExpirySensor):
    """The Cert Expiry timestamp sensor."""

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional sensor state attributes."""
        return {
            "is_valid": self.coordinator.data.is_valid,
            "error": "\n".join(self.coordinator.data.errors) or None,
        }
