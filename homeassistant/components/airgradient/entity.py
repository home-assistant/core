"""Base class for AirGradient entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirGradientCoordinator


class AirGradientEntity(Entity):
    """Defines a base AirGradient entity."""

    _attr_has_entity_name = True

    def __init__(self, serial_number: str) -> None:
        """Initialize airgradient entity."""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
        )


class AirGradientCoordinatedEntity(
    CoordinatorEntity[AirGradientCoordinator], AirGradientEntity
):
    """Defines a base AirGradient entity."""

    def __init__(self, coordinator: AirGradientCoordinator) -> None:
        """Initialize airgradient entity."""
        AirGradientEntity.__init__(self, coordinator.serial_number)
        CoordinatorEntity.__init__(self, coordinator)
