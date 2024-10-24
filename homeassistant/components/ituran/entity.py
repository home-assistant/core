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
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)

        self._license_plate = license_plate

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._vehicle.license_plate)},
            manufacturer=self._vehicle.make,
            model=self._vehicle.model,
            name=self._vehicle.model,
            serial_number=self._vehicle.license_plate,
        )

    @property
    def available(self) -> bool:
        """Return True if vehicle is still included in the account."""
        return self._license_plate in self.coordinator.data

    @property
    def _vehicle(self) -> Vehicle:
        return self.coordinator.data[self._license_plate]

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
