"""Base class for Switcher entities."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SwitcherDataUpdateCoordinator


class SwitcherEntity(CoordinatorEntity[SwitcherDataUpdateCoordinator]):
    """Base class for Switcher entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac_address)}
        )
