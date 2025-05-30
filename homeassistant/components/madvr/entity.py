"""Base class for madVR entities."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MadVRCoordinator


class MadVREntity(CoordinatorEntity[MadVRCoordinator]):
    """Defines a base madVR entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MadVRCoordinator) -> None:
        """Initialize madvr entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac)},
            name="madVR Envy",
            manufacturer="madVR",
            model="Envy",
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)},
        )
