"""Base entity for Zinvolt integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZinvoltDeviceCoordinator


class ZinvoltEntity(CoordinatorEntity[ZinvoltDeviceCoordinator]):
    """Base entity for Zinvolt integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZinvoltDeviceCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            manufacturer="Zinvolt",
            name=coordinator.battery.name,
            serial_number=coordinator.data.serial_number,
        )
