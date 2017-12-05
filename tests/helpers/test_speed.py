"""Tests Home Assistant speed helpers."""
import unittest

from tests.common import get_test_home_assistant

from homeassistant.const import (
    SPEED_KMH, PRECISION_WHOLE, SPEED_MPH, PRECISION_HALVES,
    PRECISION_TENTHS)
from homeassistant.helpers.speed import display_speed
from homeassistant.util.unit_system import METRIC_SYSTEM

SPEED = 63.913867


class TestHelpersSpeed(unittest.TestCase):
    """Setup the speed tests."""

    def setUp(self):
        """Setup the tests."""
        self.hass = get_test_home_assistant()
        self.hass.config.unit_system = METRIC_SYSTEM

    def tearDown(self):
        """Stop down stuff we started."""
        self.hass.stop()

    def test_speed_not_a_number(self):
        """Test that speed is a number."""
        temp = "Speed"
        with self.assertRaises(Exception) as context:
            display_speed(self.hass, temp, SPEED_KMH, PRECISION_HALVES)

        self.assertTrue("Speed is not a number: {}".format(temp)
                        in str(context.exception))

    def test_kmh_halves(self):
        """Test speed to celsius rounding to halves."""
        self.assertEqual(64, display_speed(
            self.hass, SPEED, SPEED_KMH, PRECISION_HALVES))

    def test_kmh_tenths(self):
        """Test speed to celsius rounding to tenths."""
        self.assertEqual(63.9, display_speed(
            self.hass, SPEED, SPEED_KMH, PRECISION_TENTHS))

    def test_mph_wholes(self):
        """Test speed rounding to wholes and converting to HA units."""
        self.assertEqual(103, display_speed(
            self.hass, SPEED, SPEED_MPH, PRECISION_WHOLE))
