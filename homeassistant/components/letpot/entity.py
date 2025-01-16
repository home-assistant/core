"""Base class for LetPot entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LetPotDeviceCoordinator


class LetPotEntity(CoordinatorEntity[LetPotDeviceCoordinator]):
    """Defines a base LetPot entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LetPotDeviceCoordinator) -> None:
        """Initialize a LetPot entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device.serial_number)},
            name=coordinator.device.name,
            manufacturer="LetPot",
            model=coordinator.device_client.device_model_name,
            model_id=coordinator.device_client.device_model_code,
            serial_number=coordinator.device.serial_number,
        )
