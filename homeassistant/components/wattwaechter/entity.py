"""Base entity for the WattWächter Plus integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WattwaechterCoordinator


class WattwaechterEntity(CoordinatorEntity[WattwaechterCoordinator]):
    """Base entity for WattWächter Plus devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WattwaechterCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator.device_name,
            manufacturer=MANUFACTURER,
            model=coordinator.model,
            sw_version=coordinator.fw_version,
            configuration_url=f"http://{coordinator.host}",
        )
        if coordinator.mac:
            self._attr_device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, coordinator.mac)
            }
