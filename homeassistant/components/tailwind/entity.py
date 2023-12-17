"""Base entity for the Tailwind integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TailwindDataUpdateCoordinator


class TailwindEntity(CoordinatorEntity[TailwindDataUpdateCoordinator]):
    """Defines an Tailwind entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TailwindDataUpdateCoordinator) -> None:
        """Initialize an Tailwind entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.device_id)},
            connections={(CONNECTION_NETWORK_MAC, coordinator.data.mac_address)},
            manufacturer="Tailwind",
            model=coordinator.data.product,
            sw_version=coordinator.data.firmware_version,
        )
