"""Counter for the days until an HTTPS (TLS) certificate will expire."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CertExpiryDataUpdateCoordinator


class CertExpiryEntity(CoordinatorEntity[CertExpiryDataUpdateCoordinator]):
    """Defines a base Cert Expiry entity."""

    _attr_has_entity_name = True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional sensor state attributes."""
        return {
            "is_valid": self.coordinator.is_cert_valid,
            "error": str(self.coordinator.cert_error),
        }
