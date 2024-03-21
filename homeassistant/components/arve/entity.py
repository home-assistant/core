"""Arve base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArveCoordinator


class ArveDeviceEntity(CoordinatorEntity[ArveCoordinator]):
    """Defines a base Arve device entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self, coordinator: ArveCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the Arve device entity."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_unique_id = (
            f"{coordinator.arve.device_sn}_{self.entity_description.translation_key}"
        )

        self.name = self.entity_description.key

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.arve.device_sn)},
            manufacturer="Calanda Air AG",
            model="Arve Sens Pro",
            serial_number=coordinator.arve.device_sn,
            name=coordinator.config_entry.title,
        )
