"""Base entity for the Elgato integration."""
from __future__ import annotations

from elgato import Elgato, Info

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class ElgatoEntity(Entity):
    """Defines an Elgato entity."""

    _attr_has_entity_name = True

    def __init__(self, client: Elgato, info: Info, mac: str | None) -> None:
        """Initialize an Elgato entity."""
        self.client = client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.serial_number)},
            manufacturer="Elgato",
            model=info.product_name,
            name=info.display_name,
            sw_version=f"{info.firmware_version} ({info.firmware_build_number})",
            hw_version=str(info.hardware_board_type),
        )
        if mac is not None:
            self._attr_device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, format_mac(mac))
            }
