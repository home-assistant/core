"""Defines a base CentriConnect entity."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CentriConnectCoordinator


class CentriConnectBaseEntity(CoordinatorEntity[CentriConnectCoordinator]):
    """Defines a base CentriConnect entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CentriConnectCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the CentriConnect entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            name=coordinator.device_info.device_name,
            serial_number=coordinator.device_info.device_id,
            hw_version=coordinator.device_info.hardware_version,
            sw_version=coordinator.device_info.lte_version,
            manufacturer="CentriConnect",
        )
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"
        self.entity_description = description
