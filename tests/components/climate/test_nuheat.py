"""The test for the NuHeat thermostat module."""
import unittest
from unittest.mock import PropertyMock, Mock, patch

from homeassistant.components.climate import (
    SUPPORT_AWAY_MODE,
    SUPPORT_HOLD_MODE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    STATE_HEAT,
    STATE_IDLE)
import homeassistant.components.climate.nuheat as nuheat
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

SCHEDULE_HOLD = 3
SCHEDULE_RUN = 1
SCHEDULE_TEMPORARY_HOLD = 2


class TestNuHeat(unittest.TestCase):
    """Tests for NuHeat climate."""

    # pylint: disable=protected-access, no-self-use

    def setUp(self):
        """Set up test variables."""
        serial_number = "12345"
        min_away_temp = None
        temperature_unit = "F"

        thermostat = Mock(
            serial_number=serial_number,
            room="Master bathroom",
            online=True,
            heating=True,
            temperature=2222,
            celsius=22,
            fahrenheit=72,
            max_celsius=69,
            max_fahrenheit=157,
            min_celsius=5,
            min_fahrenheit=41,
            schedule_mode=SCHEDULE_RUN,
            target_celsius=22,
            target_fahrenheit=72)

        thermostat.resume_schedule = Mock()

        api = Mock()
        api.get_thermostat.return_value = thermostat

        self.thermostat = nuheat.NuHeatThermostat(
            api, serial_number, min_away_temp, temperature_unit)

    @patch("homeassistant.components.climate.nuheat.NuHeatThermostat")
    def test_setup_platform(self, mocked_thermostat):
        """Test setup_platform."""
        api = Mock()
        data = {"nuheat": (api, ["12345"], 50)}

        hass = Mock()
        hass.config.units.temperature_unit.return_value = "F"
        hass.data = Mock()
        hass.data.__getitem__ = Mock(side_effect=data.__getitem__)

        config = {}
        add_devices = Mock()
        discovery_info = {}

        nuheat.setup_platform(hass, config, add_devices, discovery_info)
        thermostats = [mocked_thermostat(api, "12345", 50, "F")]
        add_devices.assert_called_once_with(thermostats, True)

    def test_name(self):
        """Test name property."""
        self.assertEqual(self.thermostat.name, "Master bathroom")

    def test_icon(self):
        """Test name property."""
        self.assertEqual(self.thermostat.icon, "mdi:thermometer")

    def test_supported_features(self):
        """Test name property."""
        features = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_HOLD_MODE |
                 SUPPORT_AWAY_MODE | SUPPORT_OPERATION_MODE)
        self.assertEqual(self.thermostat.supported_features, features)

    def test_temperature_unit(self):
        """Test temperature unit."""
        self.assertEqual(self.thermostat.temperature_unit, TEMP_FAHRENHEIT)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.temperature_unit, TEMP_CELSIUS)

    def test_current_temperature(self):
        """Test current temperature."""
        self.assertEqual(self.thermostat.current_temperature, 72)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.current_temperature, 22)

    def test_current_operation(self):
        """Test current operation."""
        self.assertEqual(self.thermostat.current_operation, STATE_HEAT)
        self.thermostat._thermostat.heating = False
        self.assertEqual(self.thermostat.current_operation, STATE_IDLE)

    def test_min_away_temp(self):
        """Test the minimum target temperature to be used in away mode."""
        self.assertEqual(self.thermostat.min_away_temp, 41)

        # User defined minimum
        self.thermostat._min_away_temp = 60
        self.assertEqual(self.thermostat.min_away_temp, 60)

        # User defined minimum below the thermostat's supported minimum
        self.thermostat._min_away_temp = 0
        self.assertEqual(self.thermostat.min_away_temp, 41)

    def test_min_temp(self):
        """Test min temp."""
        self.assertEqual(self.thermostat.min_temp, 41)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.min_temp, 5)

    def test_max_temp(self):
        """Test max temp."""
        self.assertEqual(self.thermostat.max_temp, 157)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.max_temp, 69)

    def test_target_temperature(self):
        """Test target temperature."""
        self.assertEqual(self.thermostat.target_temperature, 72)
        self.thermostat._temperature_unit = "C"
        self.assertEqual(self.thermostat.target_temperature, 22)

    @patch.object(
        nuheat.NuHeatThermostat, "is_away_mode_on", new_callable=PropertyMock)
    def test_current_hold_mode_away(self, is_away_mode_on):
        """Test current hold mode while away."""
        is_away_mode_on.return_value = True
        self.assertEqual(self.thermostat.current_hold_mode, nuheat.MODE_AWAY)

    @patch.object(
        nuheat.NuHeatThermostat, "is_away_mode_on", new_callable=PropertyMock)
    def test_current_hold_mode(self, is_away_mode_on):
        """Test current hold mode."""
        is_away_mode_on.return_value = False

        self.thermostat._thermostat.schedule_mode = SCHEDULE_RUN
        self.assertEqual(self.thermostat.current_hold_mode, nuheat.MODE_AUTO)

        self.thermostat._thermostat.schedule_mode = SCHEDULE_HOLD
        self.assertEqual(
            self.thermostat.current_hold_mode, nuheat.MODE_HOLD_TEMPERATURE)

        self.thermostat._thermostat.schedule_mode = SCHEDULE_TEMPORARY_HOLD
        self.assertEqual(
            self.thermostat.current_hold_mode, nuheat.MODE_TEMPORARY_HOLD)

    def test_is_away_mode_on(self):
        """Test is away mode on."""
        _thermostat = self.thermostat._thermostat
        _thermostat.schedule_mode = SCHEDULE_HOLD

        # user-defined minimum fahrenheit
        self.thermostat._min_away_temp = 59
        _thermostat.target_fahrenheit = 59
        self.assertTrue(self.thermostat.is_away_mode_on)

        # user-defined minimum celsius
        self.thermostat._temperature_unit = "C"
        self.thermostat._min_away_temp = 15
        _thermostat.target_celsius = 15
        self.assertTrue(self.thermostat.is_away_mode_on)

        # thermostat's minimum supported temperature
        self.thermostat._min_away_temp = None
        _thermostat.target_celsius = _thermostat.min_celsius
        self.assertTrue(self.thermostat.is_away_mode_on)

        # thermostat held at a temperature above the minimum
        _thermostat.target_celsius = _thermostat.min_celsius + 1
        self.assertFalse(self.thermostat.is_away_mode_on)

        # thermostat not on HOLD
        _thermostat.target_celsius = _thermostat.min_celsius
        _thermostat.schedule_mode = SCHEDULE_RUN
        self.assertFalse(self.thermostat.is_away_mode_on)

    @patch.object(
        nuheat.NuHeatThermostat, "is_away_mode_on", new_callable=PropertyMock)
    @patch.object(nuheat.NuHeatThermostat, "set_temperature")
    def test_turn_away_mode_on_home(self, set_temp, is_away_mode_on):
        """Test turn away mode on when not away."""
        is_away_mode_on.return_value = False
        self.thermostat.turn_away_mode_on()
        set_temp.assert_called_once_with(temperature=self.thermostat.min_temp)
        self.assertTrue(self.thermostat._force_update)

    @patch.object(
        nuheat.NuHeatThermostat, "is_away_mode_on", new_callable=PropertyMock)
    @patch.object(nuheat.NuHeatThermostat, "set_temperature")
    def test_turn_away_mode_on_away(self, set_temp, is_away_mode_on):
        """Test turn away mode on when away."""
        is_away_mode_on.return_value = True
        self.thermostat.turn_away_mode_on()
        set_temp.assert_not_called()

    @patch.object(
        nuheat.NuHeatThermostat, "is_away_mode_on", new_callable=PropertyMock)
    @patch.object(nuheat.NuHeatThermostat, "resume_program")
    def test_turn_away_mode_off_home(self, resume, is_away_mode_on):
        """Test turn away mode off when home."""
        is_away_mode_on.return_value = False
        self.thermostat.turn_away_mode_off()
        self.assertFalse(self.thermostat._force_update)
        resume.assert_not_called()

    @patch.object(
        nuheat.NuHeatThermostat, "is_away_mode_on", new_callable=PropertyMock)
    @patch.object(nuheat.NuHeatThermostat, "resume_program")
    def test_turn_away_mode_off_away(self, resume, is_away_mode_on):
        """Test turn away mode off when away."""
        is_away_mode_on.return_value = True
        self.thermostat.turn_away_mode_off()
        self.assertTrue(self.thermostat._force_update)
        resume.assert_called_once_with()

    def test_resume_program(self):
        """Test resume schedule."""
        self.thermostat.resume_program()
        self.thermostat._thermostat.resume_schedule.assert_called_once_with()
        self.assertTrue(self.thermostat._force_update)

    def test_set_temperature(self):
        """Test set temperature."""
        self.thermostat.set_temperature(temperature=85)
        self.assertEqual(self.thermostat._thermostat.target_fahrenheit, 85)
        self.assertTrue(self.thermostat._force_update)

        self.thermostat._temperature_unit = "C"
        self.thermostat.set_temperature(temperature=23)
        self.assertEqual(self.thermostat._thermostat.target_celsius, 23)
        self.assertTrue(self.thermostat._force_update)

    @patch.object(nuheat.NuHeatThermostat, "_throttled_update")
    def test_forced_update(self, throttled_update):
        """Test update without throttle."""
        self.thermostat._force_update = True
        self.thermostat.update()
        throttled_update.assert_called_once_with(no_throttle=True)
        self.assertFalse(self.thermostat._force_update)

    @patch.object(nuheat.NuHeatThermostat, "_throttled_update")
    def test_throttled_update(self, throttled_update):
        """Test update with throttle."""
        self.thermostat._force_update = False
        self.thermostat.update()
        throttled_update.assert_called_once_with()
        self.assertFalse(self.thermostat._force_update)
