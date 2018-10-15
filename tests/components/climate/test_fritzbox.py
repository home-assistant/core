"""The tests for the demo climate component."""
import unittest
from unittest.mock import Mock, patch

import requests

from homeassistant.components.climate.fritzbox import FritzboxThermostat


class TestFritzboxClimate(unittest.TestCase):
    """Test Fritz!Box heating thermostats."""

    def setUp(self):
        """Create a mock device to test on."""
        self.device = Mock()
        self.device.name = 'Test Thermostat'
        self.device.actual_temperature = 18.0
        self.device.target_temperature = 19.5
        self.device.comfort_temperature = 22.0
        self.device.eco_temperature = 16.0
        self.device.present = True
        self.device.device_lock = True
        self.device.lock = False
        self.device.battery_low = True
        self.device.set_target_temperature = Mock()
        self.device.update = Mock()
        mock_fritz = Mock()
        mock_fritz.login = Mock()
        self.thermostat = FritzboxThermostat(self.device, mock_fritz)

    def test_init(self):
        """Test instance creation."""
        self.assertEqual(18.0, self.thermostat._current_temperature)
        self.assertEqual(19.5, self.thermostat._target_temperature)
        self.assertEqual(22.0, self.thermostat._comfort_temperature)
        self.assertEqual(16.0, self.thermostat._eco_temperature)

    def test_supported_features(self):
        """Test supported features property."""
        self.assertEqual(129, self.thermostat.supported_features)

    def test_available(self):
        """Test available property."""
        self.assertTrue(self.thermostat.available)
        self.thermostat._device.present = False
        self.assertFalse(self.thermostat.available)

    def test_name(self):
        """Test name property."""
        self.assertEqual('Test Thermostat', self.thermostat.name)

    def test_temperature_unit(self):
        """Test temperature_unit property."""
        self.assertEqual('°C', self.thermostat.temperature_unit)

    def test_precision(self):
        """Test precision property."""
        self.assertEqual(0.5, self.thermostat.precision)

    def test_current_temperature(self):
        """Test current_temperature property incl. special temperatures."""
        self.assertEqual(18, self.thermostat.current_temperature)

    def test_target_temperature(self):
        """Test target_temperature property."""
        self.assertEqual(19.5, self.thermostat.target_temperature)

        self.thermostat._target_temperature = 126.5
        self.assertEqual(None, self.thermostat.target_temperature)

        self.thermostat._target_temperature = 127.0
        self.assertEqual(None, self.thermostat.target_temperature)

    @patch.object(FritzboxThermostat, 'set_operation_mode')
    def test_set_temperature_operation_mode(self, mock_set_op):
        """Test set_temperature by operation_mode."""
        self.thermostat.set_temperature(operation_mode='test_mode')
        mock_set_op.assert_called_once_with('test_mode')

    def test_set_temperature_temperature(self):
        """Test set_temperature by temperature."""
        self.thermostat.set_temperature(temperature=23.0)
        self.thermostat._device.set_target_temperature.\
            assert_called_once_with(23.0)

    @patch.object(FritzboxThermostat, 'set_operation_mode')
    def test_set_temperature_none(self, mock_set_op):
        """Test set_temperature with no arguments."""
        self.thermostat.set_temperature()
        mock_set_op.assert_not_called()
        self.thermostat._device.set_target_temperature.assert_not_called()

    @patch.object(FritzboxThermostat, 'set_operation_mode')
    def test_set_temperature_operation_mode_precedence(self, mock_set_op):
        """Test set_temperature for precedence of operation_mode arguement."""
        self.thermostat.set_temperature(operation_mode='test_mode',
                                        temperature=23.0)
        mock_set_op.assert_called_once_with('test_mode')
        self.thermostat._device.set_target_temperature.assert_not_called()

    def test_current_operation(self):
        """Test operation mode property for different temperatures."""
        self.thermostat._target_temperature = 127.0
        self.assertEqual('on', self.thermostat.current_operation)
        self.thermostat._target_temperature = 126.5
        self.assertEqual('off', self.thermostat.current_operation)
        self.thermostat._target_temperature = 22.0
        self.assertEqual('heat', self.thermostat.current_operation)
        self.thermostat._target_temperature = 16.0
        self.assertEqual('eco', self.thermostat.current_operation)
        self.thermostat._target_temperature = 12.5
        self.assertEqual('manual', self.thermostat.current_operation)

    def test_operation_list(self):
        """Test operation_list property."""
        self.assertEqual(['heat', 'eco', 'off', 'on'],
                         self.thermostat.operation_list)

    @patch.object(FritzboxThermostat, 'set_temperature')
    def test_set_operation_mode(self, mock_set_temp):
        """Test set_operation_mode by all modes and with a non-existing one."""
        values = {
            'heat': 22.0,
            'eco': 16.0,
            'on': 30.0,
            'off': 0.0}
        for mode, temp in values.items():
            print(mode, temp)

            mock_set_temp.reset_mock()
            self.thermostat.set_operation_mode(mode)
            mock_set_temp.assert_called_once_with(temperature=temp)

        mock_set_temp.reset_mock()
        self.thermostat.set_operation_mode('non_existing_mode')
        mock_set_temp.assert_not_called()

    def test_min_max_temperature(self):
        """Test min_temp and max_temp properties."""
        self.assertEqual(8.0, self.thermostat.min_temp)
        self.assertEqual(28.0, self.thermostat.max_temp)

    def test_device_state_attributes(self):
        """Test device_state property."""
        attr = self.thermostat.device_state_attributes
        self.assertEqual(attr['device_locked'], True)
        self.assertEqual(attr['locked'], False)
        self.assertEqual(attr['battery_low'], True)

    def test_update(self):
        """Test update function."""
        device = Mock()
        device.update = Mock()
        device.actual_temperature = 10.0
        device.target_temperature = 11.0
        device.comfort_temperature = 12.0
        device.eco_temperature = 13.0
        self.thermostat._device = device

        self.thermostat.update()

        device.update.assert_called_once_with()
        self.assertEqual(10.0, self.thermostat._current_temperature)
        self.assertEqual(11.0, self.thermostat._target_temperature)
        self.assertEqual(12.0, self.thermostat._comfort_temperature)
        self.assertEqual(13.0, self.thermostat._eco_temperature)

    def test_update_http_error(self):
        """Test exception handling of update function."""
        self.device.update.side_effect = requests.exceptions.HTTPError
        self.thermostat.update()
        self.thermostat._fritz.login.assert_called_once_with()
