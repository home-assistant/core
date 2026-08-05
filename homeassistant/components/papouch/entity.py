"""Base class for Papouch entities."""

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PapouchDataUpdateCoordinator


class PapouchEntity(CoordinatorEntity[PapouchDataUpdateCoordinator]):
    """Common class for all Papouch entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PapouchDataUpdateCoordinator, entry) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)

        formatted_mac = format_mac(coordinator.device.mac_address)

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, formatted_mac)},
            identifiers={(entry.domain, coordinator.device.mac_address)},
        )
