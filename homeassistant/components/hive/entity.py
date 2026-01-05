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

    def __init__(self, hive: Hive, hive_device: dict[str, Any]) -> None:
        """Initialize the instance."""
        self.hive = hive
        self.device = hive_device
        self._attr_name = self.device["haName"]
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

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )
