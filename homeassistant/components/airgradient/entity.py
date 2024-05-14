"""Base class for AirGradient entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirGradientDataUpdateCoordinator


class AirGradientEntity(CoordinatorEntity[AirGradientDataUpdateCoordinator]):
    """Defines a base AirGradient entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirGradientDataUpdateCoordinator) -> None:
        """Initialize airgradient entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            model=coordinator.data.model,
            manufacturer="AirGradient",
            serial_number=coordinator.data.serial_number,
            sw_version=coordinator.data.firmware_version,
        )
