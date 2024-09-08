"""Base class for AirGradient entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CambridgeAudioCoordinator


class CambridgeAudioEntity(CoordinatorEntity[CambridgeAudioCoordinator]):
    """Defines a base Cambridge Audio entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: CambridgeAudioCoordinator) -> None:
        """Initialize Cambridge Audio entity."""
        super().__init__(coordinator)
        info = coordinator.data.info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.udn)},
            name=info.name,
            manufacturer="Cambridge Audio",
            model=info.model,
            serial_number=info.udn,
        )
