"""Base Entity for Ecoforest."""
from __future__ import annotations

from pyecoforest.models.device import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import EcoforestCoordinator


class EcoforestEntity(CoordinatorEntity[EcoforestCoordinator]):
    """Common Ecoforest entity using CoordinatorEntity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcoforestCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize device information."""
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}_{description.key}"

        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            name=MANUFACTURER,
            model=coordinator.data.model_name,
            sw_version=coordinator.data.firmware,
            manufacturer=MANUFACTURER,
        )

    @property
    def data(self) -> Device:
        """Return ecoforest data."""
        assert self.coordinator.data
        return self.coordinator.data
