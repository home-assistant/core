"""Common entity classes for InComfort integration."""

from incomfortclient import Heater

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InComfortDataCoordinator


class IncomfortEntity(CoordinatorEntity[InComfortDataCoordinator]):
    """Base class for all InComfort entities."""

    _attr_has_entity_name = True


class IncomfortBoilerEntity(IncomfortEntity):
    """Base class for all InComfort boiler entities."""

    def __init__(self, coordinator: InComfortDataCoordinator, heater: Heater) -> None:
        """Initialize the boiler entity."""
        super().__init__(coordinator)
        self._heater = heater
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heater.serial_no)},
            manufacturer="Intergas",
            name="Boiler",
        )
