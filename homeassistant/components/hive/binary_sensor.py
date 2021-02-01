"""Support for the Hive binary sensors."""
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import DOMAIN, HiveEntity

DEVICETYPE = {
    "contactsensor": {"type": "opening"},
    "motionsensor": {"type": "motion"},
    "GLASS_BREAK": {"icon": "mdi:dock-window", "type": "sound"},
    "SMOKE_CO": {"icon": "mdi:smoke-detector", "type": "smoke"},
    "DOG_BARK": {"icon": "mdi:dog", "type": "sound"},
    "Connectivity": {"icon": "mdi:switch", "type": "connectivity"},
}
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


async def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Hive Binary Sensor.

    No longer in use.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive Binary Sensor based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.devices.get("binary_sensor")
    devs = []
    if devices:
        for dev in devices:
            devs.append(HiveBinarySensorEntity(hive, dev))
    async_add_entities(devs, True)


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
        return DEVICETYPE.get(self.device["hiveType"])["type"]

    @property
    def icon(self):
        """Return the class of this sensor."""
        return DEVICETYPE.get(self.device["hiveType"]).get("icon", None)

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
        return self.attributes

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.device["status"]["state"]

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.get_sensor(self.device)
        self.attributes = self.device.get("attributes", {})
