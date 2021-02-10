"""Support for the Hive binary sensors."""
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    BinarySensorEntity,
)

from . import ATTR_AVAILABLE, ATTR_MODE, DATA_HIVE, DOMAIN, HiveEntity

DEVICETYPE = {
    "contactsensor": DEVICE_CLASS_OPENING,
    "motionsensor": DEVICE_CLASS_MOTION,
    "Connectivity": DEVICE_CLASS_CONNECTIVITY,
}
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Hive Binary Sensor."""
    if discovery_info is None:
        return

    hive = hass.data[DOMAIN].get(DATA_HIVE)
    devices = hive.devices.get("binary_sensor")
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
        return {"identifiers": {(DOMAIN, self.unique_id)}, "name": self.name}

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
    def device_state_attributes(self):
        """Show Device Attributes."""
        return {
            ATTR_AVAILABLE: self.attributes.get(ATTR_AVAILABLE),
            ATTR_MODE: self.attributes.get(ATTR_MODE),
        }

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.device["status"]["state"]

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.get_sensor(self.device)
        self.attributes = self.device.get("attributes", {})
