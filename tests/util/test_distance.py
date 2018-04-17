"""Test homeassistant distance utility functions."""

import unittest
import homeassistant.util.distance as distance_util
from homeassistant.const import (LENGTH_KILOMETERS, LENGTH_METERS, LENGTH_FEET,
                                 LENGTH_MILES)

INVALID_SYMBOL = 'bob'
VALID_SYMBOL = LENGTH_KILOMETERS


class TestDistanceUtil(unittest.TestCase):
    """Test the distance utility functions."""

    def test_convert_same_unit(self):
        """Test conversion from any unit to same unit."""
        self.assertEqual(5,
                         distance_util.convert(5, LENGTH_KILOMETERS,
                                               LENGTH_KILOMETERS))
        self.assertEqual(2,
                         distance_util.convert(2, LENGTH_METERS,
                                               LENGTH_METERS))
        self.assertEqual(10,
                         distance_util.convert(10, LENGTH_MILES, LENGTH_MILES))
        self.assertEqual(9,
                         distance_util.convert(9, LENGTH_FEET, LENGTH_FEET))

    def test_convert_invalid_unit(self):
        """Test exception is thrown for invalid units."""
        with self.assertRaises(ValueError):
            distance_util.convert(5, INVALID_SYMBOL,
                                  VALID_SYMBOL)

        with self.assertRaises(ValueError):
            distance_util.convert(5, VALID_SYMBOL,
                                  INVALID_SYMBOL)

    def test_convert_nonnumeric_value(self):
        """Test exception is thrown for nonnumeric type."""
        with self.assertRaises(TypeError):
            distance_util.convert('a', LENGTH_KILOMETERS, LENGTH_METERS)

    def test_convert_from_miles(self):
        """Test conversion from miles to other units."""
        miles = 5
        self.assertEqual(
            distance_util.convert(miles, LENGTH_MILES, LENGTH_KILOMETERS),
            8.04672)
        self.assertEqual(
            distance_util.convert(miles, LENGTH_MILES, LENGTH_METERS),
            8046.72)
        self.assertEqual(
            distance_util.convert(miles, LENGTH_MILES, LENGTH_FEET),
            26400.0008448)

    def test_convert_from_feet(self):
        """Test conversion from feet to other units."""
        feet = 5000
        self.assertEqual(
            distance_util.convert(feet, LENGTH_FEET, LENGTH_KILOMETERS),
            1.524)
        self.assertEqual(
            distance_util.convert(feet, LENGTH_FEET, LENGTH_METERS),
            1524)
        self.assertEqual(
            distance_util.convert(feet, LENGTH_FEET, LENGTH_MILES),
            0.9469694040000001)

    def test_convert_from_kilometers(self):
        """Test conversion from kilometers to other units."""
        km = 5
        self.assertEqual(
            distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_FEET),
            16404.2)
        self.assertEqual(
            distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_METERS),
            5000)
        self.assertEqual(
            distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_MILES),
            3.106855)

    def test_convert_from_meters(self):
        """Test conversion from meters to other units."""
        m = 5000
        self.assertEqual(distance_util.convert(m, LENGTH_METERS, LENGTH_FEET),
                         16404.2)
        self.assertEqual(
            distance_util.convert(m, LENGTH_METERS, LENGTH_KILOMETERS),
            5)
        self.assertEqual(distance_util.convert(m, LENGTH_METERS, LENGTH_MILES),
                         3.106855)
