"""Entity object for shared properties of Gree entities."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DeviceDataUpdateCoordinator


class GreeEntity(CoordinatorEntity[DeviceDataUpdateCoordinator]):
    """Generic Gree entity (base class)."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DeviceDataUpdateCoordinator, desc: str | None = None
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        name = coordinator.device.device_info.name
        mac = coordinator.device.device_info.mac
        self._attr_unique_id = f"{mac}_{desc}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, mac)},
            identifiers={(DOMAIN, mac)},
            manufacturer="Gree",
            name=name,
        )
