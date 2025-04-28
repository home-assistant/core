"""Base for all turan entities."""

from __future__ import annotations

from pyituran import Vehicle

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IturanDataUpdateCoordinator


class IturanBaseEntity(CoordinatorEntity[IturanDataUpdateCoordinator]):
    """Common base for Ituran entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IturanDataUpdateCoordinator,
        license_plate: str,
        unique_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._license_plate = license_plate
        self._attr_unique_id = f"{license_plate}-{unique_key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.vehicle.license_plate)},
            manufacturer=self.vehicle.make,
            model=self.vehicle.model,
            name=self.vehicle.model,
            serial_number=self.vehicle.license_plate,
        )

    @property
    def available(self) -> bool:
        """Return True if vehicle is still included in the account."""
        return super().available and self._license_plate in self.coordinator.data

    @property
    def vehicle(self) -> Vehicle:
        """Return the vehicle information associated with this entity."""
        return self.coordinator.data[self._license_plate]
