"""
Demo platform that offers a fake thermostat.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo thermostats."""
    add_devices([
        DemoThermostat("Nest", 21, TEMP_CELSIUS, False, 19, False),
        DemoThermostat("Thermostat", 68, TEMP_FAHRENHEIT, True, 77, True),
    ])


# pylint: disable=too-many-arguments
class DemoThermostat(ThermostatDevice):
    """Representation of a demo thermostat."""

    def __init__(self, name, target_temperature, unit_of_measurement,
                 away, current_temperature, is_fan_on):
        """Initialize the thermostat."""
        self._name = name
        self._target_temperature = target_temperature
        self._unit_of_measurement = unit_of_measurement
        self._away = away
        self._current_temperature = current_temperature
        self._is_fan_on = is_fan_on

    @property
    def should_poll(self):
        """No polling needed for a demo thermostat."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    @property
    def is_fan_on(self):
        """Return true if the fan is on."""
        return self._is_fan_on

    def set_temperature(self, temperature):
        """Set new target temperature."""
        self._target_temperature = temperature

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False

    def turn_fan_on(self):
        """Turn fan on."""
        self._is_fan_on = True

    def turn_fan_off(self):
        """Turn fan off."""
        self._is_fan_on = False
