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
        self, coordinator: ArveCoordinator, description: EntityDescription, sn: str
    ) -> None:
        """Initialize the Arve device entity."""
        super().__init__(coordinator)

        self.device_sn = sn

        self.device_name = coordinator.data[self.device_sn]["info"].name

        self.entity_description = description

        self._attr_unique_id = f"{self.device_sn}_{self.entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_sn)},
            manufacturer="Calanda Air AG",
            model="Arve Sens Pro",
            serial_number=self.device_sn,
            name=self.device_name,
        )
