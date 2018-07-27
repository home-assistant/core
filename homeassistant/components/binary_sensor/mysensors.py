"""
Support for MySensors binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.mysensors/
"""
from homeassistant.components import mysensors
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES, DOMAIN, BinarySensorDevice)
from homeassistant.const import STATE_ON

SENSORS = {
    'S_DOOR': 'door',
    'S_MOTION': 'motion',
    'S_SMOKE': 'smoke',
    'S_SPRINKLER': 'safety',
    'S_WATER_LEAK': 'safety',
    'S_SOUND': 'sound',
    'S_VIBRATION': 'vibration',
    'S_MOISTURE': 'moisture',
}


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the mysensors platform for binary sensors."""
    mysensors.setup_mysensors_platform(
        hass, DOMAIN, discovery_info, MySensorsBinarySensor,
        async_add_devices=async_add_devices)


class MySensorsBinarySensor(
        mysensors.device.MySensorsEntity, BinarySensorDevice):
    """Representation of a MySensors Binary Sensor child node."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._values.get(self.value_type) == STATE_ON

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        pres = self.gateway.const.Presentation
        device_class = SENSORS.get(pres(self.child_type).name)
        if device_class in DEVICE_CLASSES:
            return device_class
        return None
