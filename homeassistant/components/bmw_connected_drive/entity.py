"""Base for all BMW entities."""

from __future__ import annotations

from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BMWDataUpdateCoordinator


class BMWBaseEntity(CoordinatorEntity[BMWDataUpdateCoordinator]):
    """Common base for BMW entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)

        self.vehicle = vehicle

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.vin)},
            manufacturer=vehicle.brand.name,
            model=vehicle.name,
            name=vehicle.name,
            serial_number=vehicle.vin,
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
