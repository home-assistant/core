"""Test temperature utility functions."""

import unittest
import homeassistant.util.temperature as temperature_util
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT


class TestTemperatureUtil(unittest.TestCase):
    """Test the temperature utility functions."""

    def test_convert_same_unit(self):
        """Test conversion from any unit to same unit."""
        self.assertEqual(20, temperature_util.convert(5, TEMP_CELSIUS,
                                                      TEMP_CELSIUS))
        self.assertEqual(20, temperature_util.convert(20, TEMP_FAHRENHEIT,
                                                      TEMP_FAHRENHEIT))
        # Try a repeating decimal to catch precision errors that might
        # crop up from round-trip conversions
        self.assertEqual(5/7, temperature_util.convert(5/7, TEMP_FAHRENHEIT,
                                                       TEMP_FAHRENHEIT))

    def test_convert_invalid_unit(self):
        """Test exception is thrown for invalid units."""
        with self.assertRaises(ValueError):
            temperature_util.convert(5, 'hotnesses', TEMP_CELSIUS)

        with self.assertRaises(ValueError):
            temperature_util.convert(5, TEMP_CELSIUS, 'brrs')

    def test_convert_nonnumeric_value(self):
        """Test exception is thrown for nonnumeric type."""
        with self.assertRaises(TypeError):
            temperature_util.convert('cold', TEMP_CELSIUS, TEMP_FAHRENHEIT)

    def test_convert_c_to_f(self):
        """Test conversion from celsius to fahrenheit."""
        self.assertEqual(
            temperature_util.convert(20, TEMP_CELSIUS, TEMP_FAHRENHEIT), 68)
        self.assertEqual(
            temperature_util.convert(-40, TEMP_CELSIUS, TEMP_FAHRENHEIT), -40)

    def test_convert_f_to_c(self):
        """Test conversion from celsius to fahrenheit."""
        self.assertEqual(
            temperature_util.convert(68, TEMP_CELSIUS, TEMP_FAHRENHEIT), 20)
        self.assertEqual(
            temperature_util.convert(-40, TEMP_CELSIUS, TEMP_FAHRENHEIT), -40)
