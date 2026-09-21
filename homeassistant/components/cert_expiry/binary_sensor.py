"""Binary sensors for the cert_expiry integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    CertExpiryConfigEntry,
    CertExpiryData,
    CertExpiryDataUpdateCoordinator,
)
from .entity import CertExpiryEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CertExpiryBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Cert Expiry binary sensor entity."""

    is_on_fn: Callable[[CertExpiryData], bool]
    reason_fn: Callable[[CertExpiryData], str | None] | None = None


PROBLEM_DESCRIPTION = CertExpiryBinarySensorEntityDescription(
    key="problem",
    translation_key="problem",
    device_class=BinarySensorDeviceClass.PROBLEM,
    is_on_fn=lambda data: data.has_problem,
    reason_fn=lambda data: data.problem_reason,
)

CERTIFICATE_INVALID_DESCRIPTION = CertExpiryBinarySensorEntityDescription(
    key="certificate_invalid",
    translation_key="certificate_invalid",
    device_class=BinarySensorDeviceClass.PROBLEM,
    is_on_fn=lambda data: not data.is_valid,
)

CHECK_DESCRIPTIONS: tuple[CertExpiryBinarySensorEntityDescription, ...] = (
    CertExpiryBinarySensorEntityDescription(
        key="certificate_untrusted",
        translation_key="certificate_untrusted",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.cert_error is not None,
        reason_fn=lambda data: data.cert_error,
    ),
    CertExpiryBinarySensorEntityDescription(
        key="tls_version_unsupported",
        translation_key="tls_version_unsupported",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.tls_version_error is not None,
        reason_fn=lambda data: data.tls_version_error,
    ),
    CertExpiryBinarySensorEntityDescription(
        key="cipher_unsupported",
        translation_key="cipher_unsupported",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.cipher_error is not None,
        reason_fn=lambda data: data.cipher_error,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CertExpiryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add cert-expiry binary sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            CertExpiryBinarySensor(coordinator, PROBLEM_DESCRIPTION),
            CertificateInvalidBinarySensor(
                coordinator, CERTIFICATE_INVALID_DESCRIPTION
            ),
            *(
                CertExpiryBinarySensor(coordinator, description)
                for description in CHECK_DESCRIPTIONS
            ),
        ]
    )


class CertExpiryBinarySensor(CertExpiryEntity, BinarySensorEntity):
    """A binary sensor reporting one check of the Cert Expiry data."""

    entity_description: CertExpiryBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: CertExpiryDataUpdateCoordinator,
        description: CertExpiryBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Cert Expiry binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the check found a problem."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if self.entity_description.reason_fn is None:
            return None
        return {"reason": self.entity_description.reason_fn(self.coordinator.data)}


class CertificateInvalidBinarySensor(CertExpiryBinarySensor):
    """Reports a certificate outside its validity period, and which end."""

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {"reason": self.coordinator.data.validity_reason}
