"""Base entity for the Flexit Nordic (BACnet) integration."""

from __future__ import annotations

from flexit_bacnet import FlexitBACnet

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlexitCoordinator


class FlexitEntity(CoordinatorEntity[FlexitCoordinator]):
    """Defines a Flexit entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FlexitCoordinator) -> None:
        """Initialize a Flexit Nordic (BACnet) entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.device.serial_number),
            },
            name=coordinator.device.device_name,
            manufacturer="Flexit",
            model="Nordic",
            model_id=coordinator.device.model,
            serial_number=coordinator.device.serial_number,
        )

    @property
    def device(self) -> FlexitBACnet:
        """Return the device."""
        return self.coordinator.data
