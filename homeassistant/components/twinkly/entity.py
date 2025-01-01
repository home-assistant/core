"""Base entity for Twinkly."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEV_MODEL, DEV_NAME, DOMAIN
from .coordinator import TwinklyCoordinator


class TwinklyEntity(CoordinatorEntity[TwinklyCoordinator]):
    """Defines a base Twinkly entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TwinklyCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        device_info = coordinator.data.device_info
        mac = device_info["mac"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer="LEDWORKS",
            model=device_info[DEV_MODEL],
            name=device_info[DEV_NAME],
            sw_version=coordinator.software_version,
        )
