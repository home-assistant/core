"""Arve base entity."""

from __future__ import annotations

from asyncarve import ArveDeviceInfo

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArveCoordinator


class ArveDeviceEntity(CoordinatorEntity[ArveCoordinator]):
    """Defines a base Arve device entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ArveCoordinator,
        description: EntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize the Arve device entity."""
        super().__init__(coordinator)

        self.device_serial_number = serial_number

        self.entity_description = description

        self._attr_unique_id = f"{serial_number}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="Calanda Air AG",
            model="Arve Sens Pro",
            serial_number=serial_number,
            name=self.device.info.name,
        )

    @property
    def available(self) -> bool:
        """Check if device is available."""
        return super()._attr_available and (
            self.device_serial_number in self.coordinator.data
        )

    @property
    def device(self) -> ArveDeviceInfo:
        """Returns device instance."""
        return self.coordinator.data[self.device_serial_number]
