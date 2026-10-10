"""Base entity for the Comet WiFi integration."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_NAME_PREFIX, DOMAIN, MANUFACTURER, MODEL
from .coordinator import CometWiFiDataCoordinator


class CometWiFiEntity(CoordinatorEntity[CometWiFiDataCoordinator]):
    """Base entity for Comet WiFi thermostats."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CometWiFiDataCoordinator) -> None:
        """Initialize the Comet WiFi entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac)},
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)},
            name=f"{DEVICE_NAME_PREFIX} {coordinator.mac}",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
