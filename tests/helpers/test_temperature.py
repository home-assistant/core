"""Tests Home Assistant temperature helpers."""
import unittest

from tests.common import get_test_home_assistant

from homeassistant.const import (
    TEMP_CELSIUS, PRECISION_WHOLE, TEMP_FAHRENHEIT, PRECISION_HALVES,
    PRECISION_TENTHS)
from homeassistant.helpers.temperature import display_temp
from homeassistant.util.unit_system import METRIC_SYSTEM

TEMP = 24.636626


class TestHelpersTemperature(unittest.TestCase):
    """Setup the temperature tests."""

    def setUp(self):
        """Setup the tests."""
        self.hass = get_test_home_assistant()
        self.hass.config.unit_system = METRIC_SYSTEM

    def tearDown(self):
        """Stop down stuff we started."""
        self.hass.stop()

    def test_temperature_not_a_number(self):
        """Test that temperature is a number."""
        temp = "Temperature"
        with self.assertRaises(Exception) as context:
            display_temp(self.hass, temp, TEMP_CELSIUS, PRECISION_HALVES)

        self.assertTrue("Temperature is not a number: {}".format(temp)
                        in str(context.exception))

    def test_celsius_halves(self):
        """Test temperature to celsius rounding to halves."""
        self.assertEqual(24.5, display_temp(
            self.hass, TEMP, TEMP_CELSIUS, PRECISION_HALVES))

    def test_celsius_tenths(self):
        """Test temperature to celsius rounding to tenths."""
        self.assertEqual(24.6, display_temp(
            self.hass, TEMP, TEMP_CELSIUS, PRECISION_TENTHS))

    def test_fahrenheit_wholes(self):
        """Test temperature to fahrenheit rounding to wholes."""
        self.assertEqual(-4, display_temp(
            self.hass, TEMP, TEMP_FAHRENHEIT, PRECISION_WHOLE))
