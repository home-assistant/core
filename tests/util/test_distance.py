"""Test homeasssitant distance utility functions."""

import unittest
import homeassistant.util.distance as distance_util

KILOMETERS = distance_util.KILOMETERS_SYMBOL
METERS = distance_util.METERS_SYMBOL
FEET = distance_util.FEET_SYMBOL
MILES = distance_util.MILES_SYMBOL

INVALID_SYMBOL = 'bob'
VALID_SYMBOL = KILOMETERS


class TestDistanceUtil(unittest.TestCase):
    """Test the distance utility functions."""

    def test_convert_same_unit(self):
        """Test conversion from any unit to same unit."""
        self.assertEqual(5, distance_util.convert(5, KILOMETERS, KILOMETERS))
        self.assertEqual(2, distance_util.convert(2, METERS, METERS))
        self.assertEqual(10, distance_util.convert(10, MILES, MILES))
        self.assertEqual(9, distance_util.convert(9, FEET, FEET))

    def test_convert_invalid_unit(self):
        """Test exception is thrown for invalid units."""
        with self.assertRaises(ValueError):
            distance_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

        with self.assertRaises(ValueError):
            distance_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)

    def test_convert_nonnumeric_value(self):
        """Test exception is thrown for nonnumeric type."""
        with self.assertRaises(TypeError):
            distance_util.convert('a', KILOMETERS, METERS)

    def test_convert_from_miles(self):
        """Test conversion from miles to other units."""
        miles = 5
        self.assertEqual(distance_util.convert(miles, MILES, KILOMETERS),
                         8.04672)
        self.assertEqual(distance_util.convert(miles, MILES, METERS), 8046.72)
        self.assertEqual(distance_util.convert(miles, MILES, FEET),
                         26400.0008448)

    def test_convert_from_feet(self):
        """Test conversion from feet to other units."""
        feet = 5000
        self.assertEqual(distance_util.convert(feet, FEET, KILOMETERS), 1.524)
        self.assertEqual(distance_util.convert(feet, FEET, METERS), 1524)
        self.assertEqual(distance_util.convert(feet, FEET, MILES),
                         0.9469694040000001)

    def test_convert_from_kilometers(self):
        """Test conversion from kilometers to other units."""
        km = 5
        self.assertEqual(distance_util.convert(km, KILOMETERS, FEET), 16404.2)
        self.assertEqual(distance_util.convert(km, KILOMETERS, METERS), 5000)
        self.assertEqual(distance_util.convert(km, KILOMETERS, MILES),
                         3.106855)

    def test_convert_from_meters(self):
        """Test conversion from meters to other units."""
        m = 5000
        self.assertEqual(distance_util.convert(m, METERS, FEET), 16404.2)
        self.assertEqual(distance_util.convert(m, METERS, KILOMETERS), 5)
        self.assertEqual(distance_util.convert(m, METERS, MILES), 3.106855)
