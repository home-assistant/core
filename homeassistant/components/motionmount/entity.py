"""Support for MotionMount sensors."""
from homeassistant.const import ATTR_CONNECTIONS, ATTR_IDENTIFIERS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EMPTY_MAC
from .coordinator import MotionMountCoordinator


class MotionMountEntity(CoordinatorEntity[MotionMountCoordinator], Entity):
    """Representation of a MotionMount entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MotionMountCoordinator) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        mac = format_mac(coordinator.mm.mac.hex())

        self._attr_device_info = DeviceInfo(
            name=coordinator.mm.name,
            manufacturer="Vogel's",
            model="TVM 7675",
        )

        if mac == EMPTY_MAC:
            assert coordinator.config_entry is not None
            self._attr_device_info[ATTR_IDENTIFIERS] = {
                (DOMAIN, coordinator.config_entry.entry_id)
            }
        else:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, mac)
            }
