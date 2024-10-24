"""Base class for all WeConnect entities."""

from weconnect import weconnect

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRAND_MAPPING, BRAND_UNKNOWN, DOMAIN
from .coordinator import WeConnectCoordinator


class WeConnectEntity(CoordinatorEntity[WeConnectCoordinator]):
    """Base class for all WeConnect entities."""

    _attr_has_entity_name = True

    vehicle: weconnect.Vehicle

    def __init__(
        self, coordinator: WeConnectCoordinator, vehicle: weconnect.Vehicle
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.vehicle = vehicle
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.vin)},
            manufacturer=BRAND_MAPPING.get(self.vehicle.brandCode.value, BRAND_UNKNOWN),
            model=self.vehicle.model.value,
            name=self.vehicle_name,
            serial_number=self.vin,
        )

    @property
    def vin(self) -> str:
        """Return the VIN of the vehicle."""
        return str(self.vehicle.vin.value)

    @property
    def vehicle_name(self) -> str:
        """Return the name of the vehicle."""
        return self.vehicle.nickname.value or self.vin

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
