"""Support for the Hive devices and services."""

from __future__ import annotations

from typing import Any

from apyhiveapi import Hive

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class HiveEntity(Entity):
    """Initiate Hive Base Class."""

    _attr_has_entity_name = True

    def __init__(self, hive: Hive, hive_device: dict[str, Any]) -> None:
        """Initialize the instance."""
        self.hive = hive
        self.device = hive_device
        self._attr_name = self._derive_entity_name(
            hive_device.get("haName"), hive_device.get("device_name")
        )
        self._attr_unique_id = f"{self.device['hiveID']}-{self.device['hiveType']}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device["device_id"])},
            model=self.device["deviceData"]["model"],
            manufacturer=self.device["deviceData"]["manufacturer"],
            name=self.device["device_name"],
            sw_version=self.device["deviceData"]["version"],
            via_device=(DOMAIN, self.device["parentDevice"]),
        )
        self.attributes: dict[str, Any] = {}

    @staticmethod
    def _derive_entity_name(ha_name: str | None, device_name: str | None) -> str | None:
        """Derive the entity name from the Hive device data.

        Because ``_attr_has_entity_name`` is True, Home Assistant prefixes the
        device name automatically. Strip the device-name prefix from ``haName``
        so it is not duplicated, and return ``None`` when the entity represents
        the device itself, when no meaningful suffix remains, or when either
        value is missing from the upstream data.
        """
        if not ha_name or not device_name or ha_name == device_name:
            return None
        if ha_name.startswith(f"{device_name} "):
            suffix = ha_name[len(device_name) + 1 :].strip()
            return suffix or None
        return ha_name

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )
