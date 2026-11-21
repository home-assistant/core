"""Base entity for the gridX integration."""

from typing import override

from gridx_connector import GridXSystem

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GridxLiveCoordinator


class GridxEntity(CoordinatorEntity[GridxLiveCoordinator]):
    """An entity belonging to one gridX system."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GridxLiveCoordinator, system: GridXSystem) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.system_id = system.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system.id)},
            name=system.name or "gridBox",
            manufacturer=system.manufacturer or "gridX",
            model=system.model or "gridBox",
            serial_number=system.serial_number,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the system was part of the last successful update."""
        return super().available and self.system_id in self.coordinator.data
