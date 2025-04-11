"""Base class for Syncthru entities."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, SyncthruCoordinator


class SyncthruEntity(CoordinatorEntity[SyncthruCoordinator]):
    """Base class for Syncthru entities."""

    def __init__(self, coordinator: SyncthruCoordinator, key: str) -> None:
        """Initialize the Syncthru entity."""
        super().__init__(coordinator)
        serial_number = coordinator.syncthru.serial_number()
        assert serial_number is not None
        self._attr_unique_id = f"{serial_number}_{key}"
        connections = set()
        if mac := coordinator.syncthru.raw().get("identity", {}).get("mac_addr"):
            connections.add((dr.CONNECTION_NETWORK_MAC, mac))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            connections=connections,
            configuration_url=coordinator.syncthru.url,
            manufacturer="Samsung",
            model=coordinator.syncthru.model(),
            name=coordinator.syncthru.hostname(),
        )
