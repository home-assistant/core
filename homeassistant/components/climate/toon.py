"""
Toon van Eneco Thermostat Support.

This provides a component for the rebranded Quby thermostat as provided by
Eneco.
"""

from homeassistant.components.climate import (ClimateDevice,
                                              ATTR_TEMPERATURE,
                                              STATE_PERFORMANCE,
                                              STATE_HEAT,
                                              STATE_ECO,
                                              STATE_COOL)
from homeassistant.const import TEMP_CELSIUS

import homeassistant.components.toon as toon_main


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup thermostat."""
    # Add toon
    add_devices((ThermostatDevice(hass), ), True)


class ThermostatDevice(ClimateDevice):
    """Interface class for the toon module and HA."""

    def __init__(self, hass):
        """Initialize the device."""
        self._name = 'Toon van Eneco'
        self.hass = hass
        self.thermos = hass.data[toon_main.TOON_HANDLE]

        # set up internal state vars
        self._state = None
        self._temperature = None
        self._setpoint = None
        self._operation_list = [STATE_PERFORMANCE,
                                STATE_HEAT,
                                STATE_ECO,
                                STATE_COOL]

    @property
    def name(self):
        """Name of this Thermostat."""
        return self._name

    @property
    def should_poll(self):
        """Polling is required."""
        return True

    @property
    def temperature_unit(self):
        """The unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation i.e. comfort, home, away."""
        state = self.thermos.get_data('state')
        return state

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.thermos.get_data('temp')

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.thermos.get_data('setpoint')

    def set_temperature(self, **kwargs):
        """Change the setpoint of the thermostat."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        self.thermos.set_temp(temp)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode as toonlib requires it."""
        toonlib_values = {STATE_PERFORMANCE: 'Comfort',
                          STATE_HEAT: 'Home',
                          STATE_ECO: 'Away',
                          STATE_COOL: 'Sleep'}

        self.thermos.set_state(toonlib_values[operation_mode])

    def update(self):
        """Update local state."""
        self.thermos.update()
