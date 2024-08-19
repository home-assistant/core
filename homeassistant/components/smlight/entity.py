"""Base class for all SMLIGHT entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER
from .coordinator import SmDataUpdateCoordinator


class SmEntity(CoordinatorEntity[SmDataUpdateCoordinator]):
    """Base class for all SMLight entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmDataUpdateCoordinator) -> None:
        """Initialize entity with device."""
        super().__init__(coordinator)
        mac = format_mac(coordinator.data.info.MAC)
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{coordinator.client.host}",
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer=ATTR_MANUFACTURER,
            model=coordinator.data.info.model,
            sw_version=f"core: {coordinator.data.info.sw_version} / zigbee: {coordinator.data.info.zb_version}",
        )
