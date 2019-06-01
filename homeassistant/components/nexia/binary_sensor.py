from homeassistant.const import (ATTR_ATTRIBUTION)
from homeassistant.components.binary_sensor import (BinarySensorDevice, DEVICE_CLASS_MOVING, DEVICE_CLASS_HEAT)
from . import (DATA_NEXIA, ATTR_MODEL, ATTR_FIRMWARE, ATTR_THERMOSTAT_NAME, ATTRIBUTION)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Nexia device."""
    thermostat = hass.data[DATA_NEXIA]

    sensors = list()

    sensors.append(NexiaBinarySensor(thermostat, "is_blower_active", "Blower Active", None))
    if thermostat.has_emergency_heat():
        sensors.append(NexiaBinarySensor(thermostat, "is_emergency_heat_active", "Emergency Heat Active", None))

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
    def device_state_attributes(self):
        """Return the device specific state attributes."""

        data = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_MODEL: self._device.get_thermostat_model(),
            ATTR_FIRMWARE: self._device.get_thermostat_firmware(),
            ATTR_THERMOSTAT_NAME: self._device.get_thermostat_name()
        }
        return data

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