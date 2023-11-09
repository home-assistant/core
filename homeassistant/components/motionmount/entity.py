"""Support for MotionMount sensors."""
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MotionMountCoordinator


class MotionMountEntity(CoordinatorEntity[MotionMountCoordinator], Entity):
    """Representation of a MotionMount entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MotionMountCoordinator) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        unique_id = format_mac(coordinator.mm.mac.hex())

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=coordinator.mm.name,
            manufacturer="Vogel's",
            model="TVM 7675",
        )
