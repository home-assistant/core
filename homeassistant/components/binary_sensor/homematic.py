"""
Support for Homematic binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.homematic/
"""
import logging
from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.binary_sensor import BinarySensorDevice
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']

SENSOR_TYPES_CLASS = {
    "Remote": None,
    "ShutterContact": "opening",
    "IPShutterContact": "opening",
    "Smoke": "smoke",
    "SmokeV2": "smoke",
    "Motion": "motion",
    "MotionV2": "motion",
    "RemoteMotion": None,
    "WeatherSensor": None,
    "TiltSensor": None,
}


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the Homematic binary sensor platform."""
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(
        HMBinarySensor,
        discovery_info,
        add_callback_devices
    )


class HMBinarySensor(homematic.HMDevice, BinarySensorDevice):
    """Representation of a binary Homematic device."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        if not self.available:
            return False
        return bool(self._hm_get_state())

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        if not self.available:
            return None

        # If state is MOTION (RemoteMotion works only)
        if self._state == "MOTION":
            return "motion"
        return SENSOR_TYPES_CLASS.get(self._hmdevice.__class__.__name__, None)

    def _init_data_struct(self):
        """Generate a data struct (self._data) from the Homematic metadata."""
        # add state to data struct
        if self._state:
            _LOGGER.debug("%s init datastruct with main node '%s'", self._name,
                          self._state)
            self._data.update({self._state: STATE_UNKNOWN})
