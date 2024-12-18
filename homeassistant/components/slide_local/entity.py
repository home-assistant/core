"""Entities for slide_local integration."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SlideCoordinator


class SlideEntity(CoordinatorEntity[SlideCoordinator]):
    """Base class of a Slide local API cover."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SlideCoordinator) -> None:
        """Initialize the Slide device."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            manufacturer="Innovation in Motion",
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.data["mac"])},
            name=coordinator.data["device_name"],
            sw_version=coordinator.api_version,
            hw_version=coordinator.data["board_rev"],
            serial_number=coordinator.data["mac"],
            configuration_url=f"http://{coordinator.host}",
        )
