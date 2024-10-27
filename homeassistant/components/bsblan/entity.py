"""BSBLan base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BSBLanData
from .const import DOMAIN
from .coordinator import BSBLanUpdateCoordinator


class BSBLanEntity(CoordinatorEntity[BSBLanUpdateCoordinator]):
    """Defines a base BSBLan entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BSBLanUpdateCoordinator, data: BSBLanData) -> None:
        """Initialize BSBLan entity."""
        super().__init__(coordinator, data)
        host = coordinator.config_entry.data["host"]
        mac = data.device.MAC
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, format_mac(mac))},
            name=data.device.name,
            manufacturer="BSBLAN Inc.",
            model=data.info.device_identification.value,
            sw_version=data.device.version,
            configuration_url=f"http://{host}",
        )
