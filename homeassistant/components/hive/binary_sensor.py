"""Support for the Hive binary sensors."""
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import HiveEntity
from .const import DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("binary_sensor")
    entities = []
    if devices:
        for dev in devices:
            entities.append(HiveBinarySensorEntity(hive, dev))
    async_add_entities(entities, True)


class HiveBinarySensorEntity(HiveEntity, BinarySensorEntity):
    """Representation of a Hive binary sensor."""

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.getSensor(self.device)
        self.attributes = self.device.get("attributes", {})
        self._attr_is_on = self.device["status"]["state"]
        if self.device["hiveType"] != "Connectivity":
            self._attr_available = self.device["deviceData"].get("online")
        else:
            self._attr_available = True
