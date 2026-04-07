"""Base entity for the Fresh-r integration."""

from __future__ import annotations

from pyfreshr.models import DeviceType

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshrReadingsCoordinator

_DEVICE_TYPE_NAMES: dict[DeviceType, str] = {
    DeviceType.FRESH_R: "Fresh-r",
    DeviceType.FORWARD: "Fresh-r Forward",
    DeviceType.MONITOR: "Fresh-r Monitor",
}


class FreshrEntity(CoordinatorEntity[FreshrReadingsCoordinator]):
    """Base class for Fresh-r entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FreshrReadingsCoordinator) -> None:
        """Initialize the Fresh-r entity."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=_DEVICE_TYPE_NAMES.get(device.device_type, "Fresh-r"),
            serial_number=device.id,
            manufacturer="Fresh-r",
        )
