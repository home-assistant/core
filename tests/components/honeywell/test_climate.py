"""The test the Honeywell thermostat module."""
import unittest
from unittest import mock

import somecomfort

import homeassistant.components.honeywell.climate as honeywellClimate
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT


class TestHoneywellUS(unittest.TestCase):
    """A test class for Honeywell US thermostats."""

    def setup_method(self, method):
        """Test the setup method."""
        self.data = mock.MagicMock()
        self.cool_away_temp = 18
        self.heat_away_temp = 28
        self.honeywellUSThermostat = honeywellClimate.HoneywellUSThermostat(
            self.data,
            self.cool_away_temp,
            self.heat_away_temp,
        )

        self.data._device.fan_running = True
        self.data._device.name = "test"
        self.data._device.temperature_unit = "F"
        self.data._device.current_temperature = 72
        self.data._device.setpoint_cool = 78
        self.data._device.setpoint_heat = 65
        self.data._device.system_mode = "heat"
        self.data._device.fan_mode = "auto"

    def test_properties(self):
        """Test the properties."""
        assert self.honeywellUSThermostat.fan_mode == "auto"
        assert self.honeywellUSThermostat.name == "test"
        assert self.honeywellUSThermostat.current_temperature == 72

    def test_unit_of_measurement(self):
        """Test the unit of measurement."""
        assert self.honeywellUSThermostat.temperature_unit == TEMP_FAHRENHEIT
        self.data._device.temperature_unit = "C"
        assert self.honeywellUSThermostat.temperature_unit == TEMP_CELSIUS

    def test_target_temp(self):
        """Test the target temperature."""
        assert self.honeywellUSThermostat.target_temperature == 65
        self.data._device.system_mode = "cool"
        assert self.honeywellUSThermostat.target_temperature == 78

    def test_set_temp(self):
        """Test setting the temperature."""
        self.honeywellUSThermostat.set_temperature(temperature=70)
        assert self.data._device.setpoint_heat == 70
        assert self.honeywellUSThermostat.target_temperature == 70

        self.data._device.system_mode = "cool"
        assert self.honeywellUSThermostat.target_temperature == 78
        self.honeywellUSThermostat.set_temperature(temperature=74)
        assert self.data._device.setpoint_cool == 74
        assert self.honeywellUSThermostat.target_temperature == 74

    def test_set_hvac_mode(self) -> None:
        """Test setting the operation mode."""
        self.honeywellUSThermostat.set_hvac_mode("cool")
        assert self.data._device.system_mode == "cool"

        self.honeywellUSThermostat.set_hvac_mode("heat")
        assert self.data._device.system_mode == "heat"

    def test_set_temp_fail(self):
        """Test if setting the temperature fails."""
        self.data._device.setpoint_heat = mock.MagicMock(
            side_effect=somecomfort.SomeComfortError
        )
        self.honeywellUSThermostat.set_temperature(temperature=123)

    def test_heat_away_mode(self):
        """Test setting the heat away mode."""
        self.honeywellUSThermostat.set_hvac_mode("heat")
        assert not self.honeywellUSThermostat._away
        self.honeywellUSThermostat._turn_away_mode_on()
        assert self.honeywellUSThermostat._away
        assert self.data._device.setpoint_heat == self.heat_away_temp
        assert self.data._device.hold_heat is True

        self.honeywellUSThermostat._turn_away_mode_off()
        assert not self.honeywellUSThermostat._away
        assert self.data._device.hold_heat is False
