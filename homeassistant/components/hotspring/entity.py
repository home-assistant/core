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
        identifier = info.mac_address or info.root_topic
        self._attr_unique_id = f"{identifier}_{key}"
        connections = set()
        if info.mac_address:
            connections.add((CONNECTION_NETWORK_MAC, info.mac_address))
        self._attr_device_info = DeviceInfo(
            connections=connections,
            identifiers={(DOMAIN, identifier)},
            name=info.hostname or "Hot Spring Spa",
            manufacturer="Hot Spring",
            model="Connected Spa",
        )
