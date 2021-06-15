"""Support for the Hive binary sensors."""
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_SOUND,
    BinarySensorEntity,
)

from . import HiveEntity
from .const import ATTR_MODE, DOMAIN

DEVICETYPE = {
    "contactsensor": DEVICE_CLASS_OPENING,
    "motionsensor": DEVICE_CLASS_MOTION,
    "Connectivity": DEVICE_CLASS_CONNECTIVITY,
    "SMOKE_CO": DEVICE_CLASS_SMOKE,
    "DOG_BARK": DEVICE_CLASS_SOUND,
    "GLASS_BREAK": DEVICE_CLASS_SOUND,
}
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

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.device["device_id"])},
            "name": self.device["device_name"],
            "model": self.device["deviceData"]["model"],
            "manufacturer": self.device["deviceData"]["manufacturer"],
            "sw_version": self.device["deviceData"]["version"],
            "via_device": (DOMAIN, self.device["parentDevice"]),
        }

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICETYPE.get(self.device["hiveType"])

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self.device["haName"]

    @property
    def available(self):
        """Return if the device is available."""
        if self.device["hiveType"] != "Connectivity":
            return self.device["deviceData"]["online"]
        return True

    @property
    def extra_state_attributes(self):
        """Show Device Attributes."""
        return {
            ATTR_MODE: self.attributes.get(ATTR_MODE),
        }

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.device["status"]["state"]

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.getSensor(self.device)
        self.attributes = self.device.get("attributes", {})
