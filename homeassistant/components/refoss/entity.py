"""Entity object for shared properties of Refoss entities."""
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .bridge import DeviceDataUpdateCoordinator
from .const import DOMAIN


class RefossEntity(CoordinatorEntity[DeviceDataUpdateCoordinator]):
    """Refoss entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DeviceDataUpdateCoordinator, channel: int) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        name = coordinator.device.dev_name
        mac = coordinator.device.mac
        if channel == 0:
            self._attr_name = None
        else:
            self._attr_name = str(channel)

        self._attr_unique_id = f"{mac}_{channel}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, mac)},
            identifiers={(DOMAIN, mac)},
            manufacturer="Refoss",
            name=name,
        )
