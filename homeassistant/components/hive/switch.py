"""Support for the Hive switches."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HiveEntity, refresh_system
from .const import DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("switch")
    entities = []
    if devices:
        for dev in devices:
            entities.append(HiveDevicePlug(hive, dev))
    async_add_entities(entities, True)


class HiveDevicePlug(HiveEntity, SwitchEntity):
    """Hive Active Plug."""

    @refresh_system
    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.hive.switch.turnOn(self.device)

    @refresh_system
    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.hive.switch.turnOff(self.device)

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.switch.getSwitch(self.device)
        self._attr_available = self.device["deviceData"].get("online")
        self._attr_current_power_w = self.device["status"].get("power_usage")
        self._attr_is_on = self.device["status"]["state"]
        self.attributes.update(self.device.get("attributes", {}))
