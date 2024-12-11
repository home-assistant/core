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

        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name="Cookidoo",
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Vorwerk International & Co. KmG",
            model="Cookidoo - Thermomix® recipe portal",
            configuration_url="https://cookidoo.ch",  # coordinator.cookidoo.localization["url"],
        )
