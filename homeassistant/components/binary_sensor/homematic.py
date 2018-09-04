"""
Support for HomeMatic binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.homematic/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.homematic import ATTR_DISCOVER_DEVICES, HMDevice
from homeassistant.const import STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']

SENSOR_TYPES_CLASS = {
    'IPShutterContact': 'opening',
    'MaxShutterContact': 'opening',
    'Motion': 'motion',
    'MotionV2': 'motion',
    'PresenceIP': 'motion',
    'Remote': None,
    'RemoteMotion': None,
    'ShutterContact': 'opening',
    'Smoke': 'smoke',
    'SmokeV2': 'smoke',
    'TiltSensor': None,
    'WeatherSensor': None,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HomeMatic binary sensor platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMBinarySensor(conf)
        devices.append(new_device)

    add_entities(devices)


class HMBinarySensor(HMDevice, BinarySensorDevice):
    """Representation of a binary HomeMatic device."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        if not self.available:
            return False
        return bool(self._hm_get_state())

    @property
    def device_class(self):
        """Return the class of this sensor from DEVICE_CLASSES."""
        # If state is MOTION (Only RemoteMotion working)
        if self._state == 'MOTION':
            return 'motion'
        return SENSOR_TYPES_CLASS.get(self._hmdevice.__class__.__name__, None)

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        # Add state to data struct
        if self._state:
            self._data.update({self._state: STATE_UNKNOWN})
