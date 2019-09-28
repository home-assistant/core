"""Support for Ecobee binary sensors."""
from homeassistant.components.binary_sensor import (
    BinarySensorDevice,
    DEVICE_CLASS_OCCUPANCY,
)

from .const import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up ecobee binary sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up ecobee binary (occupancy) sensors."""
    data = hass.data[DOMAIN]
    dev = list()
    for index in range(len(data.ecobee.thermostats)):
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor["capability"]:
                if item["type"] != "occupancy":
                    continue

                dev.append(EcobeeBinarySensor(data, sensor["name"], index))

    async_add_entities(dev, True)


class EcobeeBinarySensor(BinarySensorDevice):
    """Representation of an Ecobee sensor."""

    def __init__(self, data, sensor_name, sensor_index):
        """Initialize the Ecobee sensor."""
        self.data = data
        self._name = sensor_name + " Occupancy"
        self.sensor_name = sensor_name
        self.index = sensor_index
        self._state = None

    @property
    def name(self):
        """Return the name of the Ecobee sensor."""
        return self._name.rstrip()

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state == "true"

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return DEVICE_CLASS_OCCUPANCY

    async def async_update(self):
        """Get the latest state of the sensor."""
        await self.data.update()
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            for item in sensor["capability"]:
                if item["type"] == "occupancy" and self.sensor_name == sensor["name"]:
                    self._state = item["value"]
