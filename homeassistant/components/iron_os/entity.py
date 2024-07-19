"""Base entity for Pinecil integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MANUFACTURER, MODEL
from .coordinator import PinecilCoordinator


class PinecilBaseEntity(CoordinatorEntity[PinecilCoordinator]):
    """Base Pinecil entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PinecilCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        )
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
        self.device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name="Pinecil",
            sw_version=coordinator.device.build,
            serial_number=f"{coordinator.device.device_sn} (ID:{coordinator.device.device_id})",
        )
