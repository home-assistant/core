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

    return homematic.setup_hmdevice_discovery_helper(
        HMSwitch,
        discovery_info,
        add_callback_devices
    )


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

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        # Use STATE
        self._state = "STATE"
        self._data.update({self._state: STATE_UNKNOWN})

        # Need sensor values for SwitchPowermeter
        for node in self._hmdevice.SENSORNODE:
            self._data.update({node: STATE_UNKNOWN})
