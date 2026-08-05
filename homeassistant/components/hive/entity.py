"""Support for the Hive devices and services."""

from typing import TYPE_CHECKING, Any, override

from apyhiveapi import Hive

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

if TYPE_CHECKING:
    from . import HiveConfigEntry


class HiveEntity(Entity):
    """Initiate Hive Base Class."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HiveConfigEntry,
        hive: Hive,
        hive_device: dict[str, Any],
    ) -> None:
        """Initialize the instance."""
        self.hive = hive
        self.device = hive_device
        self._attr_name = self.device["haName"]
        self._attr_unique_id = f"{self.device['hiveID']}-{self.device['hiveType']}"
        device_id = self.device["device_id"]
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            model=self.device["deviceData"]["model"],
            manufacturer=self.device["deviceData"]["manufacturer"],
            name=self.device["device_name"],
            sw_version=self.device["deviceData"]["version"],
        )
        # Hive reports the hub itself as its parent.
        if self.device["parentDevice"] != device_id:
            device_info["via_device_id"] = dr.async_get_device_id_by_identifier(
                hass,
                (DOMAIN, self.device["parentDevice"]),
                config_entry_id=entry.entry_id,
            )
        self._attr_device_info = device_info
        self.attributes: dict[str, Any] = {}

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )
