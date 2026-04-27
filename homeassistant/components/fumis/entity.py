"""Base entity for the Fumis integration."""

from __future__ import annotations

from homeassistant.const import CONF_MAC
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FumisDataUpdateCoordinator


class FumisEntity(CoordinatorEntity[FumisDataUpdateCoordinator]):
    """Defines a Fumis entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FumisDataUpdateCoordinator) -> None:
        """Initialize a Fumis entity."""
        super().__init__(coordinator=coordinator)
        info = coordinator.data
        mac = format_mac(coordinator.config_entry.data[CONF_MAC])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer=info.controller.manufacturer or "Fumis",
            model=info.controller.model_name,
            name=info.controller.model_name or "Pellet stove",
            sw_version=str(info.controller.version),
            hw_version=str(info.unit.version),
        )
