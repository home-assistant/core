"""Base class for AirGradient entities."""

from airgradient import get_model_name

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirGradientCoordinator


class AirGradientEntity(CoordinatorEntity[AirGradientCoordinator]):
    """Defines a base AirGradient entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirGradientCoordinator) -> None:
        """Initialize airgradient entity."""
        super().__init__(coordinator)
        measures = coordinator.data.measures
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            manufacturer="AirGradient",
            model=get_model_name(measures.model),
            model_id=measures.model,
            serial_number=coordinator.serial_number,
            sw_version=measures.firmware_version,
        )
