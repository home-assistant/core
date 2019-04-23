"""Support for HomeMatic binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.homematic import ATTR_BATTERY_DEVICES
from homeassistant.const import STATE_UNKNOWN, DEVICE_CLASS_BATTERY

from . import ATTR_DISCOVER_DEVICES, HMDevice

_LOGGER = logging.getLogger(__name__)

ATTR_LOW_BAT = 'LOW_BAT'
ATTR_LOWBAT = 'LOWBAT'

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
    battery_devices = discovery_info[ATTR_BATTERY_DEVICES]

    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        if battery_devices:
            battery_device = conf.get(ATTR_LOWBAT) or conf.get(ATTR_LOW_BAT)
            if battery_device:
                new_device = HMBatterySensor(conf)
        else:
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


class HMBatterySensor(HMDevice, BinarySensorDevice):
    """Representation of an HomeMatic low battery sensor."""

    @property
    def device_class(self):
        """Return battery as a device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def is_on(self):
        """Return True if battery is low."""
        is_on = self._data.get(ATTR_LOW_BAT, False) or self._data.get(
            ATTR_LOWBAT, False
        )
        return is_on

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        # Add state to data struct
        if self._state:
            self._data.update({self._state: STATE_UNKNOWN})
