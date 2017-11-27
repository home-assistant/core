"""Test homeassistant speed utility functions."""

import unittest
import homeassistant.util.speed as speed_util
from homeassistant.const import (SPEED_MS, SPEED_KMH, SPEED_FTS, SPEED_MPH,
                                 UNIT_AUTOCONVERT)

INVALID_SYMBOL = 'bob'
VALID_SYMBOL = SPEED_KMH


class TestDistanceUtil(unittest.TestCase):
    """Test the distance utility functions."""

    def test_convert_same_unit(self):
        """Test conversion from any unit to same unit."""
        self.assertEqual(5,
                         speed_util.convert(5, SPEED_KMH, SPEED_KMH))
        self.assertEqual(2,
                         speed_util.convert(2, SPEED_MS, SPEED_MS))
        self.assertEqual(10,
                         speed_util.convert(10, SPEED_MPH, SPEED_MPH))
        self.assertEqual(9,
                         speed_util.convert(9, SPEED_FTS, SPEED_FTS))

    def test_convert_invalid_unit(self):
        """Test exception is thrown for invalid units."""
        with self.assertRaises(ValueError):
            speed_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

        with self.assertRaises(ValueError):
            speed_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)

    def test_convert_nonnumeric_value(self):
        """Test exception is thrown for nonnumeric type."""
        with self.assertRaises(TypeError):
            speed_util.convert('a', SPEED_KMH, SPEED_MS)

    def test_convert_from_miles(self):
        """Test conversion from miles to other units."""
        miles = 5
        self.assertEqual(speed_util.convert(miles, SPEED_MPH, SPEED_KMH),
                         8.04672)
        self.assertEqual(speed_util.convert(miles, SPEED_MPH, SPEED_MS),
                         2.2352)
        self.assertEqual(speed_util.convert(miles, SPEED_MPH, SPEED_FTS),
                         7.333333568)

    def test_convert_from_feet(self):
        """Test conversion from feet to other units."""
        feet = 5000
        self.assertEqual(speed_util.convert(feet, SPEED_FTS, SPEED_KMH),
                         5486.400000000001)
        self.assertEqual(speed_util.convert(feet, SPEED_FTS, SPEED_MS),
                         1524)
        self.assertEqual(speed_util.convert(feet, SPEED_FTS, SPEED_MPH),
                         3409.0965600000004)

    def test_convert_from_kilometers(self):
        """Test conversion from kilometers to other units."""
        kilometer = 5
        self.assertEqual(speed_util.convert(kilometer, SPEED_KMH, SPEED_FTS),
                         4.556722225867599)
        self.assertEqual(speed_util.convert(kilometer, SPEED_KMH, SPEED_MS),
                         1.3888888899999998)
        self.assertEqual(speed_util.convert(kilometer, SPEED_KMH, SPEED_MPH),
                         3.1068611135966)

    def test_convert_from_meters(self):
        """Test conversion from meters to other units."""
        meter = 5000
        self.assertEqual(speed_util.convert(meter, SPEED_MS, SPEED_FTS),
                         16404.2)
        self.assertEqual(speed_util.convert(meter, SPEED_MS, SPEED_KMH),
                         18000)
        self.assertEqual(speed_util.convert(meter, SPEED_MS, SPEED_MPH),
                         11184.7)

    def test_autoconvert(self):
        """Test automatic conversion of units."""
        self.assertEqual(speed_util.convert(5000, SPEED_MS, UNIT_AUTOCONVERT),
                         16404.2)
        self.assertEqual(speed_util.convert(5000, SPEED_FTS, UNIT_AUTOCONVERT),
                         1524)
        self.assertEqual(speed_util.convert(5, SPEED_MPH, UNIT_AUTOCONVERT),
                         8.04672)
        self.assertEqual(speed_util.convert(5, SPEED_KMH, UNIT_AUTOCONVERT),
                         3.1068611135966)
