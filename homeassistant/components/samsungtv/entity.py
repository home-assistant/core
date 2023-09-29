"""Base SamsungTV Entity."""
from __future__ import annotations

from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .bridge import SamsungTVBridge
from .const import CONF_MANUFACTURER, DOMAIN


class SamsungTVEntity(Entity):
    """Defines a base SamsungTV entity."""

    def __init__(self, *, bridge: SamsungTVBridge, config_entry: ConfigEntry) -> None:
        """Initialize the SamsungTV entity."""
        self._bridge = bridge
        self._mac = config_entry.data.get(CONF_MAC)
        self._attr_name = config_entry.data.get(CONF_NAME)
        # Fallback for legacy models that doesn't have a API to retrieve MAC or SerialNumber
        self._attr_unique_id = config_entry.unique_id or config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            # Instead of setting the device name to the entity name, samsungtv
            # should be updated to set has_entity_name = True
            name=cast(str | None, self.name),
            manufacturer=config_entry.data.get(CONF_MANUFACTURER),
            model=config_entry.data.get(CONF_MODEL),
        )
        if self.unique_id:
            self._attr_device_info["identifiers"] = {(DOMAIN, self.unique_id)}
        if self._mac:
            self._attr_device_info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, self._mac)
            }
