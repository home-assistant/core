"""
The homematic binary sensor platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.homematic/

Important: For this platform to work the homematic component has to be
properly configured.

Configuration (single channel, simple device):

binary_sensor:
  - platform: homematic
    address: "<Homematic address for device>" # e.g. "JEQ0XXXXXXX"
    name: "<User defined name>" (optional)


Configuration (multiple channels, like motion detector with buttons):

binary_sensor:
  - platform: homematic
    address: "<Homematic address for device>" # e.g. "JEQ0XXXXXXX"
    param: <MOTION|PRESS_SHORT...> (device-dependent) (optional)
    button: n (integer of channel to map, device-dependent) (optional)
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
    "Motion": "motion",
    "MotionV2": "motion",
    "RemoteMotion": None
}

SUPPORT_HM_EVENT_AS_BINMOD = [
    "PRESS_LONG",
    "PRESS_SHORT"
]


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
            available_bin = self._create_binary_list_from_hm()
            for binary in available_bin:
                try:
                    if binary in self._data and self._data[binary] == 1:
                        return True
                except (ValueError, TypeError):
                    _LOGGER.warning("%s datatype error!", self._name)
            return False

        # single binary
        return bool(self._hm_get_state())

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        if not self.available:
            return None

        # If state is MOTION (RemoteMotion works only)
        if self._state in "MOTION":
            return "motion"
        return SENSOR_TYPES_CLASS.get(self._hmdevice.__class__.__name__, None)

    def _check_hm_to_ha_object(self):
        """Check if possible to use the HM Object as this HA type."""
        from pyhomematic.devicetypes.sensors import HMBinarySensor\
            as pyHMBinarySensor

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # check if the homematic device correct for this HA device
        if not isinstance(self._hmdevice, pyHMBinarySensor):
            _LOGGER.critical("This %s can't be use as binary!", self._name)
            return False

        # load possible binary sensor
        available_bin = self._create_binary_list_from_hm()

        # if exists user value?
        if self._state and self._state not in available_bin:
            _LOGGER.critical("This %s have no binary with %s!", self._name,
                             self._state)
            return False

        # only check and give a warining to User
        if self._state is None and len(available_bin) > 1:
            _LOGGER.warning("%s have multible binary params. It use all " +
                            "binary nodes as one. Possible param values: %s",
                            self._name, str(available_bin))

        return True

    def _init_data_struct(self):
        """Generate a data struct (self._data) from hm metadata."""
        super()._init_data_struct()

        # load possible binary sensor
        available_bin = self._create_binary_list_from_hm()

        # object have 1 binary
        if self._state is None and len(available_bin) == 1:
            for value in available_bin:
                self._state = value

        # no binary is definit, use all binary for state
        if self._state is None and len(available_bin) > 1:
            for node in available_bin:
                self._data.update({node: STATE_UNKNOWN})

        # add state to data struct
        if self._state:
            _LOGGER.debug("%s init datastruct with main node '%s'", self._name,
                          self._state)
            self._data.update({self._state: STATE_UNKNOWN})

    def _create_binary_list_from_hm(self):
        """Generate a own metadata for binary_sensors."""
        bin_data = {}
        if not self._hmdevice:
            return bin_data

        # copy all data from BINARYNODE
        bin_data.update(self._hmdevice.BINARYNODE)

        # copy all hm event they are supportet by this object
        for event, channel in self._hmdevice.EVENTNODE.items():
            if event in SUPPORT_HM_EVENT_AS_BINMOD:
                bin_data.update({event: channel})

        return bin_data
