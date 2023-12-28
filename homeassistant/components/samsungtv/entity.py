"""Base SamsungTV Entity."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .bridge import SamsungTVBridge
from .const import CONF_MANUFACTURER, DOMAIN


class SamsungTVEntity(Entity):
    """Defines a base SamsungTV entity."""

    _attr_has_entity_name = True

    def __init__(self, *, bridge: SamsungTVBridge, config_entry: ConfigEntry) -> None:
        """Initialize the SamsungTV entity."""
        self._bridge = bridge
        self._mac = config_entry.data.get(CONF_MAC)
        # Fallback for legacy models that doesn't have a API to retrieve MAC or SerialNumber
        self._attr_unique_id = config_entry.unique_id or config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            name=config_entry.data.get(CONF_NAME),
            manufacturer=config_entry.data.get(CONF_MANUFACTURER),
            model=config_entry.data.get(CONF_MODEL),
        )
        if self.unique_id:
            self._attr_device_info[ATTR_IDENTIFIERS] = {(DOMAIN, self.unique_id)}
        if self._mac:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, self._mac)
            }
