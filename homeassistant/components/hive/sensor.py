"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hive/
"""

from datetime import timedelta

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from . import DOMAIN, HiveEntity

DEPENDENCIES = ["hive"]
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)
DEVICETYPE = {
    "Battery": {"icon": "mdi:thermometer", "unit": " % ", "type": "battery"},
}


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Hive Sensor.

    No longer in use.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive Sensor based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.devices.get("sensor")

    devs = []
    if devices:
        for dev in devices:
            if dev["hiveType"] in DEVICETYPE:
                devs.append(HiveSensorEntity(hive, dev))
    async_add_entities(devs, True)


class HiveSensorEntity(HiveEntity, Entity):
    """Hive Sensor Entity."""

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
    def available(self):
        """Return if sensor is available."""
        return self.device.get("deviceData", {}).get("online", True)

    @property
    def device_class(self):
        """Device class of the entity."""
        return DEVICETYPE[self.device["hiveType"]].get("type", None)

    @property
    def icon(self):
        """Return the icon to use."""
        return icon_for_battery_level(
            battery_level=self.device["deviceData"]["battery"]
        )

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return DEVICETYPE[self.device["hiveType"]].get("unit", None)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.device["haName"]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device["status"]["state"]

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.attributes

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.get_sensor(self.device)
