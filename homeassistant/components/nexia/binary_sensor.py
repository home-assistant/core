from homeassistant.const import (ATTR_ATTRIBUTION)
from homeassistant.components.binary_sensor import (BinarySensorDevice)
from homeassistant.util import Throttle
from . import (DATA_NEXIA, ATTR_MODEL, ATTR_FIRMWARE, ATTR_THERMOSTAT_NAME, ATTRIBUTION, NEXIA_DEVICE, NEXIA_SCAN_INTERVAL)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Nexia device."""
    thermostat = hass.data[DATA_NEXIA][NEXIA_DEVICE]
    scan_interval = hass.data[DATA_NEXIA][NEXIA_SCAN_INTERVAL]

    sensors = list()

    sensors.append(NexiaBinarySensor(thermostat, scan_interval, "is_blower_active", "Blower Active", None))
    if thermostat.has_emergency_heat():
        sensors.append(NexiaBinarySensor(thermostat, scan_interval, "is_emergency_heat_active", "Emergency Heat Active", None))

    add_entities(sensors, True)


def percent_conv(val):
    return val * 100.0


class NexiaBinarySensor(BinarySensorDevice):

    def __init__(self, device, scan_interval, sensor_call, sensor_name, sensor_class):
        """Initialize the Ecobee sensor."""
        self._device = device
        self._name = sensor_name
        self.sensor_name = sensor_name
        self._call = sensor_call
        self._state = None
        self._device_class = sensor_class
        self.update = Throttle(scan_interval)(self._update)


    @property
    def name(self):
        """Return the name of the sensor."""
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

    def _update(self):
        """Get the latest state of the sensor."""
        self._device.update()
