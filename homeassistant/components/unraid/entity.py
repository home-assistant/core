"""Base class for KAТ Bulgaria entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UnraidUpdateCoordinator


class UnraidEntity(CoordinatorEntity[UnraidUpdateCoordinator]):
    """Defines a base AirGradient entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UnraidUpdateCoordinator) -> None:
        """Initialize airgradient entity."""

        super().__init__(coordinator)
        self._attr_unique_id: str = coordinator.client.unraid_host
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)}, manufacturer="Unraid"
        )
