"""Support for HomeMatic binary sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_PRESENCE,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)

from .const import ATTR_DISCOVER_DEVICES, ATTR_DISCOVERY_TYPE, DISCOVER_BATTERY
from .entity import HMDevice

SENSOR_TYPES_CLASS = {
    "IPShutterContact": DEVICE_CLASS_OPENING,
    "IPShutterContactSabotage": DEVICE_CLASS_OPENING,
    "MaxShutterContact": DEVICE_CLASS_OPENING,
    "Motion": DEVICE_CLASS_MOTION,
    "MotionV2": DEVICE_CLASS_MOTION,
    "PresenceIP": DEVICE_CLASS_PRESENCE,
    "Remote": None,
    "RemoteMotion": None,
    "ShutterContact": DEVICE_CLASS_OPENING,
    "Smoke": DEVICE_CLASS_SMOKE,
    "SmokeV2": DEVICE_CLASS_SMOKE,
    "TiltSensor": None,
    "WeatherSensor": None,
    "IPContact": DEVICE_CLASS_OPENING,
    "MotionIPV2": DEVICE_CLASS_MOTION,
    "IPRemoteMotionV2": DEVICE_CLASS_MOTION,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HomeMatic binary sensor platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        if discovery_info[ATTR_DISCOVERY_TYPE] == DISCOVER_BATTERY:
            devices.append(HMBatterySensor(conf))
        else:
            devices.append(HMBinarySensor(conf))

    add_entities(devices, True)


class HMBinarySensor(HMDevice, BinarySensorEntity):
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
        if self._state == "MOTION":
            return DEVICE_CLASS_MOTION
        return SENSOR_TYPES_CLASS.get(self._hmdevice.__class__.__name__)

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        # Add state to data struct
        if self._state:
            self._data.update({self._state: None})


class HMBatterySensor(HMDevice, BinarySensorEntity):
    """Representation of an HomeMatic low battery sensor."""

    @property
    def device_class(self):
        """Return battery as a device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def is_on(self):
        """Return True if battery is low."""
        return bool(self._hm_get_state())

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        # Add state to data struct
        if self._state:
            self._data.update({self._state: None})
