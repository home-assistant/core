"""Base entity for the LoJack integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LoJackCoordinator, LoJackVehicleData


class LoJackEntity(CoordinatorEntity[LoJackCoordinator]):
    """Define a base LoJack entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LoJackCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._vehicle = coordinator.data

        # Generate device name
        device_name = self._generate_device_name()

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=device_name,
            manufacturer="Spireon",
            model=self._generate_model_string(),
            serial_number=self._vehicle.vin if self._vehicle else None,
        )

    def _generate_device_name(self) -> str:
        """Generate a friendly device name."""
        if not self._vehicle:
            return f"Vehicle {self.coordinator.device_id}"

        if self._vehicle.year and self._vehicle.make and self._vehicle.model:
            return f"{self._vehicle.year} {self._vehicle.make} {self._vehicle.model}"
        if self._vehicle.make and self._vehicle.model:
            return f"{self._vehicle.make} {self._vehicle.model}"
        if self._vehicle.name:
            return self._vehicle.name
        return f"Vehicle {self.coordinator.device_id}"

    def _generate_model_string(self) -> str | None:
        """Generate model string for device info."""
        if not self._vehicle:
            return None
        if self._vehicle.make and self._vehicle.model:
            return f"{self._vehicle.make} {self._vehicle.model}"
        if self._vehicle.make:
            return self._vehicle.make
        return None

    @property
    def vehicle_data(self) -> LoJackVehicleData | None:
        """Return the current vehicle data."""
        return self.coordinator.data
