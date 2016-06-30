"""
Support for Homematic switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.homematic/
"""
import logging
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import STATE_UNKNOWN
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the Homematic switch platform."""
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(HMSwitch,
                                                     discovery_info,
                                                     add_callback_devices)


class HMSwitch(homematic.HMDevice, SwitchDevice):
    """Representation of a Homematic switch."""

    @property
    def is_on(self):
        """Return True if switch is on."""
        try:
            return self._hm_get_state() > 0
        except TypeError:
            return False

    @property
    def current_power_mwh(self):
        """Return the current power usage in mWh."""
        if "ENERGY_COUNTER" in self._data:
            try:
                return self._data["ENERGY_COUNTER"] / 1000
            except ZeroDivisionError:
                return 0

        return None

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.available:
            self._hmdevice.on(self._channel)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.available:
            self._hmdevice.off(self._channel)

    def _check_hm_to_ha_object(self):
        """Check if possible to use the Homematic object as this HA type."""
        from pyhomematic.devicetypes.actors import Dimmer, Switch

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # Check if the Homematic device is correct for this HA device
        if isinstance(self._hmdevice, Switch):
            return True
        if isinstance(self._hmdevice, Dimmer):
            return True

        _LOGGER.critical("This %s can't be use as switch", self._name)
        return False

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        from pyhomematic.devicetypes.actors import Dimmer,\
            Switch, SwitchPowermeter

        super()._init_data_struct()

        # Use STATE
        if isinstance(self._hmdevice, Switch):
            self._state = "STATE"

        # Use LEVEL
        if isinstance(self._hmdevice, Dimmer):
            self._state = "LEVEL"

        # Need sensor values for SwitchPowermeter
        if isinstance(self._hmdevice, SwitchPowermeter):
            for node in self._hmdevice.SENSORNODE:
                self._data.update({node: STATE_UNKNOWN})

        # Add state to data dict
        if self._state:
            _LOGGER.debug("%s init data dict with main node '%s'", self._name,
                          self._state)
            self._data.update({self._state: STATE_UNKNOWN})
        else:
            _LOGGER.critical("Can't correctly init light %s.", self._name)
