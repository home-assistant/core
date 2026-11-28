"""Base entity for the cert_expiry integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CertExpiryDataUpdateCoordinator


class CertExpiryEntity(CoordinatorEntity[CertExpiryDataUpdateCoordinator]):
    """Defines a base Cert Expiry entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CertExpiryDataUpdateCoordinator, key: str) -> None:
        """Initialize a Cert Expiry entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.host}:{coordinator.port}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.host}:{coordinator.port}")},
            name=coordinator.name,
            entry_type=DeviceEntryType.SERVICE,
        )
