"""Base entity for the CatGenie integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CatGenieDeviceCoordinator


class CatGenieEntity(CoordinatorEntity[CatGenieDeviceCoordinator]):
    """Defines a CatGenie entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CatGenieDeviceCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the CatGenie entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.data.mac_address)},
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator.data.name,
            manufacturer="PetNovations",
            model="CatGenie AI",
            sw_version=coordinator.data.fw_version,
            hw_version=coordinator.data.hw_revision,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data.is_online
