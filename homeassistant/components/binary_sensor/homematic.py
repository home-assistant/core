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
    "Smoke": "smoke",
    "SmokeV2": "smoke",
    "Motion": "motion",
    "MotionV2": "motion",
    "RemoteMotion": None
}


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the Homematic binary sensor platform."""
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(HMBinarySensor,
                                                     discovery_info,
                                                     add_callback_devices)


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

    def _check_hm_to_ha_object(self):
        """Check if possible to use the HM Object as this HA type."""
        from pyhomematic.devicetypes.sensors import HMBinarySensor\
            as pyHMBinarySensor

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # check if the Homematic device correct for this HA device
        if not isinstance(self._hmdevice, pyHMBinarySensor):
            _LOGGER.critical("This %s can't be use as binary", self._name)
            return False

        # if exists user value?
        if self._state and self._state not in self._hmdevice.BINARYNODE:
            _LOGGER.critical("This %s have no binary with %s", self._name,
                             self._state)
            return False

        # only check and give a warning to the user
        if self._state is None and len(self._hmdevice.BINARYNODE) > 1:
            _LOGGER.critical("%s have multiple binary params. It use all "
                             "binary nodes as one. Possible param values: %s",
                             self._name, str(self._hmdevice.BINARYNODE))
            return False

        return True

    def _init_data_struct(self):
        """Generate a data struct (self._data) from the Homematic metadata."""
        super()._init_data_struct()

        # object have 1 binary
        if self._state is None and len(self._hmdevice.BINARYNODE) == 1:
            for value in self._hmdevice.BINARYNODE:
                self._state = value

        # add state to data struct
        if self._state:
            _LOGGER.debug("%s init datastruct with main node '%s'", self._name,
                          self._state)
            self._data.update({self._state: STATE_UNKNOWN})
