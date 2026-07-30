"""Entity for Hot Spring."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HotSpringDataUpdateCoordinator


class HotSpringEntity(CoordinatorEntity[HotSpringDataUpdateCoordinator]):
    """Defines a base Hot Spring entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HotSpringDataUpdateCoordinator, key: str) -> None:
        """Initialize a base Hot Spring entity."""
        super().__init__(coordinator)
        info = self.coordinator.data.info
        self._attr_unique_id = f"{info.mac_address}_{key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, info.mac_address)},
            identifiers={(DOMAIN, info.mac_address)},
            name=info.hostname or "Hot Spring Spa",
            manufacturer="Hot Spring",
            model=info.model or "Connected Spa",
        )
