"""Base entity for the Elgato integration."""
from __future__ import annotations

from homeassistant.const import CONF_MAC
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElgatoDataUpdateCoordinator


class ElgatoEntity(CoordinatorEntity[ElgatoDataUpdateCoordinator]):
    """Defines an Elgato entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ElgatoDataUpdateCoordinator) -> None:
        """Initialize an Elgato entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.info.serial_number)},
            manufacturer="Elgato",
            model=coordinator.data.info.product_name,
            name=coordinator.data.info.display_name,
            sw_version=f"{coordinator.data.info.firmware_version} ({coordinator.data.info.firmware_build_number})",
            hw_version=str(coordinator.data.info.hardware_board_type),
        )
        if (mac := coordinator.config_entry.data.get(CONF_MAC)) is not None:
            self._attr_device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, format_mac(mac))
            }
