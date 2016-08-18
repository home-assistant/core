"""
The homematic sensor platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.homematic/

Important: For this platform to work the homematic component has to be
properly configured.
"""

import logging
from homeassistant.const import STATE_UNKNOWN
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']

HM_STATE_HA_CAST = {
    "RotaryHandleSensor": {0: "closed", 1: "tilted", 2: "open"},
    "WaterSensor": {0: "dry", 1: "wet", 2: "water"}
}

HM_UNIT_HA_CAST = {
    "HUMIDITY": "%",
    "TEMPERATURE": "°C",
    "BRIGHTNESS": "#",
    "POWER": "W",
    "CURRENT": "mA",
    "VOLTAGE": "V",
    "ENERGY_COUNTER": "Wh",
    "GAS_POWER": "m3",
    "GAS_ENERGY_COUNTER": "m3",
    "LUX": "lux"
}


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(HMSensor,
                                                     discovery_info,
                                                     add_callback_devices)


class HMSensor(homematic.HMDevice):
    """Represents various Homematic sensors in Home Assistant."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.available:
            return STATE_UNKNOWN

        # Does a cast exist for this class?
        name = self._hmdevice.__class__.__name__
        if name in HM_STATE_HA_CAST:
            return HM_STATE_HA_CAST[name].get(self._hm_get_state(), None)

        # No cast, return original value
        return self._hm_get_state()

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if not self.available:
            return None

        return HM_UNIT_HA_CAST.get(self._state, None)

    def _check_hm_to_ha_object(self):
        """Check if possible to use the HM Object as this HA type."""
        from pyhomematic.devicetypes.sensors import HMSensor as pyHMSensor

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # Check if the homematic device is correct for this HA device
        if not isinstance(self._hmdevice, pyHMSensor):
            _LOGGER.critical("This %s can't be use as sensor!", self._name)
            return False

        # Does user defined value exist?
        if self._state and self._state not in self._hmdevice.SENSORNODE:
            # pylint: disable=logging-too-many-args
            _LOGGER.critical("This %s have no sensor with %s! Values are",
                             self._name, self._state,
                             str(self._hmdevice.SENSORNODE.keys()))
            return False

        # No param is set and more than 1 sensor nodes are present
        if self._state is None and len(self._hmdevice.SENSORNODE) > 1:
            _LOGGER.critical("This %s has multiple sensor nodes. " +
                             "Please us param. Values are: %s", self._name,
                             str(self._hmdevice.SENSORNODE.keys()))
            return False

        _LOGGER.debug("%s is okay for linking", self._name)
        return True

    def _init_data_struct(self):
        """Generate a data dict (self._data) from hm metadata."""
        super()._init_data_struct()

        if self._state is None and len(self._hmdevice.SENSORNODE) == 1:
            for value in self._hmdevice.SENSORNODE:
                self._state = value

        # Add state to data dict
        if self._state:
            _LOGGER.debug("%s init datadict with main node '%s'", self._name,
                          self._state)
            self._data.update({self._state: STATE_UNKNOWN})
        else:
            _LOGGER.critical("Can't correctly init sensor %s.", self._name)
