"""Base class for Papouch entities."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PapouchDataUpdateCoordinator


class PapouchEntity(CoordinatorEntity[PapouchDataUpdateCoordinator]):
    """Common class for all Papouch entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.device.mac_address)},
            identifiers={(DOMAIN, coordinator.device.mac_address)},
        )
