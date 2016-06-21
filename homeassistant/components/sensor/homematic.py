"""
The homematic sensor platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.homematic/

Important: For this platform to work the homematic component has to be
properly configured.

Configuration:

sensor:
  - platform: homematic
    address: <Homematic address for device> # e.g. "JEQ0XXXXXXX"
    name: <User defined name> (optional)
    param: <Name of datapoint to us as sensor> (optional)
"""

import logging
from homeassistant.const import STATE_UNKNOWN
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']

HM_STATE_HA_CAST = {
    "RotaryHandleSensor", {0: "closed", 1: "tilted", 2: "open"}
}


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    return homematic.setup_hmdevice_entity_helper(HMSensor,
                                                  config,
                                                  add_callback_devices)


class HMSensor(homematic.HMDevice):
    """Represents diverse Homematic sensors in Home Assistant."""

    @property
    def state(self):
        """Return the state of the sensor (0=closed, 1=tilted, 2=open)."""
        if not self.available:
            return STATE_UNKNOWN

        # if exists a cast for that class?
        name = self._hmdevice.__class__.__name__
        if name in HM_STATE_HA_CAST:
            return HM_STATE_HA_CAST[name].get(self._get_state(), None)
        return self._get_state()

    def _check_hm_to_ha_object(self):
        """
        Check if possible to use the HM Object as this HA type
        NEED overwrite by inheret!
        """
        from pyhomematic.devicetypes.sensors import HMSensor

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # check if the homematic device correct for this HA device
        if not isinstance(self._hmdevice, HMSensor):
            _LOGGER.critical("This %s can't be use as sensor!" % self._name)
            return False

        # if exists user value?
        if self._state and not (self._state in self._hmdevice.SENSORNODE):
            _LOGGER.critical("This %s have no sensor with %s!" %
                             (self._name, self._state))
            return False

        # no param is set and more than 1 sensor node are present
        if self._state is None and len(self._hmdevice.SENSORNODE) > 1:
            _LOGGER.critical("This %s have more sensore node. " +
                             "Please us param." % self._name)
            return False

        return True

    def _init_data_struct(self):
        """
        Generate a data struct (self._data) from hm metadata
        NEED overwrite by inheret!
        """
        if self._state is None and len(self._hmdevice.SENSORNODE) == 1:
            for value in self._hmdevice.SENSORNODE:
                self._state = value

        # add state to data struct
        if self._state:
            self._set_state(STATE_UNKNOWN)
        else:
            _LOGGER.critical("Can't correct init sensor %s." % self._name)
