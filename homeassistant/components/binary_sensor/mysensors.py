"""
Support for MySensors binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.mysensors/
"""
from homeassistant.components import mysensors
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES, DOMAIN, BinarySensorDevice)
from homeassistant.const import STATE_ON


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MySensors platform for binary sensors."""
    mysensors.setup_mysensors_platform(
        hass, DOMAIN, discovery_info, MySensorsBinarySensor,
        add_devices=add_devices)


class MySensorsBinarySensor(mysensors.MySensorsEntity, BinarySensorDevice):
    """Representation of a MySensors Binary Sensor child node."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._values.get(self.value_type) == STATE_ON

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        pres = self.gateway.const.Presentation
        class_map = {
            pres.S_DOOR: 'opening',
            pres.S_MOTION: 'motion',
            pres.S_SMOKE: 'smoke',
        }
        if float(self.gateway.protocol_version) >= 1.5:
            class_map.update({
                pres.S_SPRINKLER: 'sprinkler',
                pres.S_WATER_LEAK: 'leak',
                pres.S_SOUND: 'sound',
                pres.S_VIBRATION: 'vibration',
                pres.S_MOISTURE: 'moisture',
            })
        if class_map.get(self.child_type) in DEVICE_CLASSES:
            return class_map.get(self.child_type)
