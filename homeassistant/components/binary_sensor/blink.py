"""
Support for Blink system camera control.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.blink/
"""
from homeassistant.components.blink import DOMAIN
from homeassistant.components.binary_sensor import BinarySensorDevice

DEPENDENCIES = ['blink']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the blink binary sensors."""
    if discovery_info is None:
        return

    data = hass.data[DOMAIN].blink
    devs = list()
    for name in data.cameras:
        devs.append(BlinkCameraMotionSensor(name, data))
    devs.append(BlinkSystemSensor(data))
    add_devices(devs, True)


class BlinkCameraMotionSensor(BinarySensorDevice):
    """Representation of a Blink binary sensor."""

    def __init__(self, name, data):
        """Initialize the sensor."""
        self._name = 'blink_' + name + '_motion_enabled'
        self._camera_name = name
        self.data = data
        self._state = self.data.cameras[self._camera_name].armed

    @property
    def name(self):
        """Return the name of the blink sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state

    def update(self):
        """Update sensor state."""
        self.data.refresh()
        self._state = self.data.cameras[self._camera_name].armed


class BlinkSystemSensor(BinarySensorDevice):
    """A representation of a Blink system sensor."""

    def __init__(self, data):
        """Initialize the sensor."""
        self._name = 'blink armed status'
        self.data = data
        self._state = self.data.arm

    @property
    def name(self):
        """Return the name of the blink sensor."""
        return self._name.replace(" ", "_")

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state

    def update(self):
        """Update sensor state."""
        self.data.refresh()
        self._state = self.data.arm
