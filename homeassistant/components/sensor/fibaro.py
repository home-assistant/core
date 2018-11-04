"""
Support for Fibaro sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fibaro/
"""
import logging

from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.fibaro import (
    FIBARO_CONTROLLER, FIBARO_DEVICES, FibaroDevice)

SENSOR_TYPES = {
    'com.fibaro.temperatureSensor':
        ['Temperature', None, None,
         DEVICE_CLASS_TEMPERATURE],
    'com.fibaro.smokeSensor': ['Smoke', 'ppm', 'mdi:fire', None],
    'CO2': ['CO2', 'ppm', 'mdi:cloud', None],
    'com.fibaro.humiditySensor': ['Humidity', '%', None,
                                  DEVICE_CLASS_HUMIDITY],
    'com.fibaro.lightSensor': ['Light', 'lx', None,
                               DEVICE_CLASS_ILLUMINANCE],
}

DEPENDENCIES = ['fibaro']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fibaro controller devices."""
    add_entities(
        [FibaroSensor(device, hass.data[FIBARO_CONTROLLER])
         for device in hass.data[FIBARO_DEVICES]['sensor']], True)


class FibaroSensor(FibaroDevice, Entity):
    """Representation of a Fibaro Sensor."""

    _icon = None
    _device_class = None
    _unit_of_measurement = None

    def __init__(self, fibaro_device, controller):
        """Initialize the sensor."""
        self.current_value = None
        self.last_changed_time = None
        FibaroDevice.__init__(self, fibaro_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)
        if fibaro_device.type in SENSOR_TYPES.keys():
            self._device_class = SENSOR_TYPES[fibaro_device.type][3]
            self._icon = SENSOR_TYPES[fibaro_device.type][2]
            self._unit_of_measurement = SENSOR_TYPES[fibaro_device.type][1]

    @property
    def state(self):
        """Return the name of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        try:
            if self._unit_of_measurement:
                return self._unit_of_measurement
            if self.fibaro_device.properties.unit == 'lux':
                return 'lx'
            if self.fibaro_device.properties.unit == 'C':
                return TEMP_CELSIUS
            if self.fibaro_device.properties.unit == 'F':
                return TEMP_FAHRENHEIT
            return self.fibaro_device.properties.unit
        except (KeyError, ValueError):
            pass
        return ''

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    def update(self):
        """Update the state."""
        try:
            self.current_value = float(self.fibaro_device.properties.value)
        except (KeyError, ValueError):
            pass
