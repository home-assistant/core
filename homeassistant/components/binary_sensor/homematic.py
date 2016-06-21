"""
The homematic binary sensor platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.homematic/

Important: For this platform to work the homematic component has to be
properly configured.

Configuration (single channel):

binary_sensor:
  - platform: homematic
    address: "<Homematic address for device>" # e.g. "JEQ0XXXXXXX"
    name: "<User defined name>" (optional)


Configuration (multiple channels):

binary_sensor:
  - platform: homematic
    address: "<Homematic address for device>" # e.g. "JEQ0XXXXXXX"
    button: n (integer of channel to map, device-dependent)
    name: "<User defined name>" (optional)
binary_sensor:
  - platform: homematic
  ...
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
    "Motion": "moving",
    "MotionV2": "moving",
    "RemoteMotion": None
}


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    return homematic.setup_hmdevice_entity_helper(HMBinarySensor,
                                                  config,
                                                  add_callback_devices)


class HMBinarySensor(homematic.HMDevice, BinarySensorDevice):
    """Represents diverse binary Homematic units in Home Assistant."""

    @property
    def is_on(self):
        """Return True if switch is on."""
        if not self.available:
            return False
        # no binary is defined, check all!
        if self._state is None:
            for binary in self._hmdevice.BINARYNODE:
                if self._data[binary] == 1:
                    return True
            return False

        # single binary
        return bool(self._hm_get_state())

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        if not self.available:
            return None
        return SENSOR_TYPES_CLASS.get(self._hmdevice.__class__.__name__, None)

    def _check_hm_to_ha_object(self):
        """
        Check if possible to use the HM Object as this HA type
        NEED overwrite by inheret!
        """
        from pyhomematic.devicetypes.sensors import HMBinarySensor\
            as pyHMBinarySensor

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # check if the homematic device correct for this HA device
        if not isinstance(self._hmdevice, pyHMBinarySensor):
            _LOGGER.critical("This %s can't be use as binary!", self._name)
            return False

        # if exists user value?
        if self._state and self._state not in self._hmdevice.BINARYNODE:
            _LOGGER.critical("This %s have no binary with %s!", self._name,
                             self._state)
            return False

        # only check and give a warining to User
        if self._state is None and len(self._hmdevice.BINARYNODE) > 1:
            _LOGGER.warning("This %s have more than one binary.", self._name)

        return True

    def _init_data_struct(self):
        """
        Generate a data struct (self._data) from hm metadata
        NEED overwrite by inheret!
        """
        super()._init_data_struct()

        # object have 1 binary
        if self._state is None and len(self._hmdevice.BINARYNODE) == 1:
            for value in self._hmdevice.SENSORNODE:
                self._state = value

        # no binary is definit, use all binary for state
        if self._state is None and len(self._hmdevice.BINARYNODE) > 1:
            for node in self._hmdevice.BINARYNODE:
                self._data.update({node: STATE_UNKNOWN})

        # add state to data struct
        if self._state:
            self._data.update({self._state: STATE_UNKNOWN})
