"""Support for the Hive sesnors."""

from datetime import timedelta

from homeassistant.components.sensor import DEVICE_CLASS_BATTERY
from homeassistant.helpers.entity import Entity

from . import ATTR_AVAILABLE, DATA_HIVE, DOMAIN, HiveEntity

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)
DEVICETYPE = {
    "Battery": {"unit": " % ", "type": DEVICE_CLASS_BATTERY},
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Hive Sensor."""
    if discovery_info is None:
        return

    hive = hass.data[DOMAIN].get(DATA_HIVE)
    devices = hive.devices.get("sensor")
    entities = []
    if devices:
        for dev in devices:
            if dev["hiveType"] in DEVICETYPE:
                entities.append(HiveSensorEntity(hive, dev))
    async_add_entities(entities, True)


class HiveSensorEntity(HiveEntity, Entity):
    """Hive Sensor Entity."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self.unique_id)}, "name": self.name}

    @property
    def available(self):
        """Return if sensor is available."""
        return self.device.get("deviceData", {}).get("online")

    @property
    def device_class(self):
        """Device class of the entity."""
        return DEVICETYPE[self.device["hiveType"]].get("type")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return DEVICETYPE[self.device["hiveType"]].get("unit")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.device["haName"]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device["status"]["state"]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_AVAILABLE: self.attributes.get(ATTR_AVAILABLE)}

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.get_sensor(self.device)
