"""Test homeasssitant distance utility functions."""

import unittest
import homeassistant.util.speed as speed_util
from homeassistant.const import (SPEED_KILOMETERS_PER_HOUR,
                                 SPEED_MILES_PER_HOUR,
                                 SPEED_METERS_PER_SECOND)

INVALID_SYMBOL = 'bob'
VALID_SYMBOL = SPEED_KILOMETERS_PER_HOUR


class TestSpeedUtil(unittest.TestCase):
    """Test the speed utility functions."""

    def test_convert_same_unit(self):
        """Test conversion from any unit to same unit."""
        self.assertEqual(5,
                         speed_util.convert(5, SPEED_KILOMETERS_PER_HOUR,
                                            SPEED_KILOMETERS_PER_HOUR))
        self.assertEqual(2,
                         speed_util.convert(2, SPEED_MILES_PER_HOUR,
                                            SPEED_MILES_PER_HOUR))
        self.assertEqual(10,
                         speed_util.convert(10, SPEED_METERS_PER_SECOND,
                                            SPEED_METERS_PER_SECOND))

    def test_convert_invalid_unit(self):
        """Test exception is thrown for invalid units."""
        with self.assertRaises(ValueError):
            speed_util.convert(5, INVALID_SYMBOL,
                               VALID_SYMBOL)

        with self.assertRaises(ValueError):
            speed_util.convert(5, VALID_SYMBOL,
                               INVALID_SYMBOL)

    def test_convert_nonnumeric_value(self):
        """Test exception is thrown for nonnumeric type."""
        with self.assertRaises(TypeError):
            speed_util.convert('a', SPEED_KILOMETERS_PER_HOUR,
                               SPEED_MILES_PER_HOUR)

    def test_convert_from_mph(self):
        """Test conversion from mph to other units."""
        mph = 5
        self.assertEqual(
            speed_util.convert(mph, SPEED_MILES_PER_HOUR,
                               SPEED_KILOMETERS_PER_HOUR),
            8.0467)
        self.assertEqual(
            speed_util.convert(mph, SPEED_MILES_PER_HOUR,
                               SPEED_METERS_PER_SECOND),
            2.2351962326)

    def test_convert_from_mps(self):
        """Test conversion from m/s to other units."""
        mps = 10
        self.assertEqual(
            speed_util.convert(mps, SPEED_METERS_PER_SECOND,
                               SPEED_KILOMETERS_PER_HOUR),
            36)
        self.assertEqual(
            speed_util.convert(mps, SPEED_METERS_PER_SECOND,
                               SPEED_MILES_PER_HOUR),
            22.369356)

    def test_convert_from_kph(self):
        """Test conversion from kph to other units."""
        kph = 5
        self.assertEqual(
            speed_util.convert(kph, SPEED_KILOMETERS_PER_HOUR,
                               SPEED_MILES_PER_HOUR),
            3.106855)
        self.assertEqual(
            speed_util.convert(kph, SPEED_KILOMETERS_PER_HOUR,
                               SPEED_METERS_PER_SECOND),
            1.3888900000000002)
