"""Support for HomeMatic switches."""
from homeassistant.components.switch import SwitchEntity

from .const import ATTR_DISCOVER_DEVICES
from .entity import HMDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HomeMatic switch platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMSwitch(conf)
        devices.append(new_device)

    add_entities(devices, True)


class HMSwitch(HMDevice, SwitchEntity):
    """Representation of a HomeMatic switch."""

    @property
    def is_on(self):
        """Return True if switch is on."""
        try:
            return self._hm_get_state() > 0
        except TypeError:
            return False

    @property
    def today_energy_kwh(self):
        """Return the current power usage in kWh."""
        if "ENERGY_COUNTER" in self._data:
            try:
                return self._data["ENERGY_COUNTER"] / 1000
            except ZeroDivisionError:
                return 0

        return None

    @property
    def icon(self):
        """Set lock icon for INHIBIT switches."""
        if self._state == "INHIBIT":
            if self.is_on:
                return "mdi:lock"
            return "mdi:lock-open"
        return super().icon

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._state == "INHIBIT":
            self._hmdevice.set_inhibit(True, self._channel)
        else:
            self._hmdevice.on(self._channel)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._state == "INHIBIT":
            self._hmdevice.set_inhibit(False, self._channel)
        else:
            self._hmdevice.off(self._channel)

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        if self._state is None:
            self._state = "STATE"
        self._data.update({self._state: None})

        # Need sensor values for SwitchPowermeter
        if self._state != "INHIBIT":
            for node in self._hmdevice.SENSORNODE:
                self._data.update({node: None})
