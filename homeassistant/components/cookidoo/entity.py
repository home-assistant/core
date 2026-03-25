"""Base entity for the Cookidoo integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CookidooDataUpdateCoordinator


class CookidooBaseEntity(CoordinatorEntity[CookidooDataUpdateCoordinator]):
    """Cookidoo base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CookidooDataUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        assert coordinator.config_entry.unique_id

        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name="Cookidoo",
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            manufacturer="Vorwerk International & Co. KmG",
            model="Cookidoo - Thermomix® recipe portal",
        )
