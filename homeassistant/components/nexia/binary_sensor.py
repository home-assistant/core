from homeassistant.components.binary_sensor import (BinarySensorDevice, DEVICE_CLASS_MOVING, DEVICE_CLASS_HEAT)
from . import DATA_NEXIA

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Nexia device."""
    thermostat = hass.data[DATA_NEXIA]

    sensors = list()

    sensors.append(NexiaBinarySensor(thermostat, "is_blower_active", "nexia_blower_active", DEVICE_CLASS_MOVING))
    if thermostat.has_emergency_heat():
        sensors.append(NexiaBinarySensor(thermostat, "is_emergency_heat_active", "nexia_emergency_heat_active", DEVICE_CLASS_HEAT))

    add_entities(sensors, True)

def percent_conv(val):
    return val * 100.0

class NexiaBinarySensor(BinarySensorDevice):

    def __init__(self, device, sensor_call, sensor_name, sensor_class):
        """Initialize the Ecobee sensor."""
        self._device = device
        self._name = sensor_name
        self.sensor_name = sensor_name
        self._call = sensor_call
        self._state = None
        self._device_class = sensor_class

    @property
    def name(self):
        """Return the name of the Ecobee sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return getattr(self._device, self._call)()

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._device_class

    def update(self):
        """Get the latest state of the sensor."""
        self._device.update()