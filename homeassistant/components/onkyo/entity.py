"""Onkyo integration entities."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import BRAND_NAME


class OnkyoEntity(Entity):
    """Representation of Onkyo entity."""

    _attr_has_entity_name = True

    def __init__(self, data: MappingProxyType[str, Any]) -> None:
        """Initialize an Onkyo entity."""
        super().__init__()

        mac_str = data[CONF_MAC]
        mac = ":".join(mac_str[i : i + 2] for i in range(0, len(mac_str), 2))
        self._attr_unique_id = mac_str
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, mac)},
            name=data[CONF_NAME],
            manufacturer=BRAND_NAME,
            model=data[CONF_MODEL],
        )
