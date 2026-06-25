"""Base class for all SMLIGHT entities."""

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER
from .coordinator import SmBaseDataUpdateCoordinator, sw_version_from_info


class SmEntity(CoordinatorEntity[SmBaseDataUpdateCoordinator]):
    """Base class for all SMLight entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmBaseDataUpdateCoordinator) -> None:
        """Initialize entity with device."""
        super().__init__(coordinator)
        info = coordinator.data.info
        mac = format_mac(info.MAC)
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{coordinator.client.host}",
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer=ATTR_MANUFACTURER,
            model=info.model,
            sw_version=sw_version_from_info(info),
        )
