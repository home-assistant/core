"""Base entity for the Flexit Nordic (BACnet) integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlexitCoordinator


class FlexitEntity(CoordinatorEntity[FlexitCoordinator]):
    """Defines a Flexit entity."""

    def __init__(self, coordinator: FlexitCoordinator) -> None:
        """Initialize a Flexit Nordic (BACnet) entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.device.serial_number),
            },
            name=coordinator.device.device_name,
            manufacturer="Flexit",
            model="Nordic",
            serial_number=coordinator.device.serial_number,
        )
