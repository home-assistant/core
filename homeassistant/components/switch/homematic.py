"""
The homematic switch platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.homematic/

Important: For this platform to work the homematic component has to be
properly configured.

Configuration:

switch:
  - platform: homematic
    address: <Homematic address for device> # e.g. "JEQ0XXXXXXX"
    name: <User defined name> (optional)
    button: n (integer of channel to map, device-dependent)
"""

import logging
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import STATE_UNKNOWN
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    return homematic.setup_hmdevice_entity_helper(HMSwitch,
                                                  config,
                                                  add_callback_devices)


class HMSwitch(homematic.HMDevice, SwitchDevice):
    """Represents an Homematic Switch in Home Assistant."""

    @property
    def is_on(self):
        """Return True if switch is on."""
        return bool(self._get_state())

    @property
    def current_power_mwh(self):
        """Return the current power usage in mWh."""
        if "ENERGY_COUNTER" in self._data:
            return self._data["ENERGY_COUNTER"] * 1000

        return None

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.available:
            self._hmdevice.on(self._channel)
            self._set_state(True)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.available:
            self._hmdevice.off(self._channel)
            self._set_state(False)

    def _check_hm_to_ha_object(self):
        """
        Check if possible to use the HM Object as this HA type
        NEED overwrite by inheret!
        """
        from pyhomematic.devicetypes.actors import Dimmer, Switch

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # check if the homematic device correct for this HA device
        if isinstance(self._hmdevice, Switch):
            return True
        if isinstance(self._hmdevice, Dimmer):
            return True

        _LOGGER.critical("This %s can't be use as switch!", self._name)
        return False

    def _init_data_struct(self):
        """
        Generate a data struct (self._data) from hm metadata
        NEED overwrite by inheret!
        """
        from pyhomematic.devicetypes.actors import Dimmer,\
            Switch, SwitchPowermeter

        # use STATE
        if isinstance(self._hmdevice, Switch):
            self._state = "STATE"

        # use LEVEL
        if isinstance(self._hmdevice, Dimmer):
            self._state = "LEVEL"

        # need sensor value for SwitchPowermeter
        if isinstance(self._hmdevice, SwitchPowermeter):
            for node in self._hmdevice.SENSORNODE:
                self._data.update({node: STATE_UNKNOWN})

        # add state to data struct
        if self._state:
            self._set_state(STATE_UNKNOWN)
        else:
            _LOGGER.critical("Can't correct init sensor %s.", self._name)
