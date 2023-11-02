"""Support for MotionMount sensors."""
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class MotionMountEntity(CoordinatorEntity, Entity):
    """Representation of a MotionMount entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        unique_id = format_mac(self.coordinator.mm.mac.hex())

        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self.coordinator.mm.name,
            manufacturer="Vogel's",
            model="TVM 7675",  # TODO: This is not compatible with MainSteam motorized
        )
