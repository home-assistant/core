"""Support for Ecobee sensors."""
from pyecobee.const import ECOBEE_STATE_CALIBRATING, ECOBEE_STATE_UNKNOWN

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

SENSOR_TYPES = {
    "temperature": ["Temperature", TEMP_FAHRENHEIT],
    "humidity": ["Humidity", "%"],
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up ecobee sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up ecobee (temperature and humidity) sensors."""
    data = hass.data[DOMAIN]
    dev = list()
    for index in range(len(data.ecobee.thermostats)):
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor["capability"]:
                if item["type"] not in ("temperature", "humidity"):
                    continue

                dev.append(EcobeeSensor(data, sensor["name"], item["type"], index))

    async_add_entities(dev, True)


class EcobeeSensor(Entity):
    """Representation of an Ecobee sensor."""

    def __init__(self, data, sensor_name, sensor_type, sensor_index):
        """Initialize the sensor."""
        self.data = data
        self._name = "{} {}".format(sensor_name, SENSOR_TYPES[sensor_type][0])
        self.sensor_name = sensor_name
        self.type = sensor_type
        self.index = sensor_index
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the Ecobee sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] == self.sensor_name:
                if "code" in sensor:
                    return f"{sensor['code']}-{self.device_class}"
                thermostat = self.data.ecobee.get_thermostat(self.index)
                return f"{thermostat['identifier']}-{sensor['id']}-{self.device_class}"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self.type in (DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE):
            return self.type
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state in [ECOBEE_STATE_CALIBRATING, ECOBEE_STATE_UNKNOWN, "unknown"]:
            return None

        if self.type == "temperature":
            return float(self._state) / 10

        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest state of the sensor."""
        await self.data.update()
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            for item in sensor["capability"]:
                if item["type"] != self.type:
                    continue
                self._state = item["value"]
                break
