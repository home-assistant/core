"""Test homeassistant volume utility functions."""

import unittest
import homeassistant.util.volume as volume_util
from homeassistant.const import (VOLUME_LITERS, VOLUME_MILLILITERS,
                                 VOLUME_GALLONS, VOLUME_FLUID_OUNCE)

INVALID_SYMBOL = 'bob'
VALID_SYMBOL = VOLUME_LITERS


class TestVolumeUtil(unittest.TestCase):
    """Test the volume utility functions."""

    def test_convert_same_unit(self):
        """Test conversion from any unit to same unit."""
        self.assertEqual(2, volume_util.convert(2, VOLUME_LITERS,
                                                VOLUME_LITERS))
        self.assertEqual(3, volume_util.convert(3, VOLUME_MILLILITERS,
                                                VOLUME_MILLILITERS))
        self.assertEqual(4, volume_util.convert(4, VOLUME_GALLONS,
                                                VOLUME_GALLONS))
        self.assertEqual(5, volume_util.convert(5, VOLUME_FLUID_OUNCE,
                                                VOLUME_FLUID_OUNCE))

    def test_convert_invalid_unit(self):
        """Test exception is thrown for invalid units."""
        with self.assertRaises(ValueError):
            volume_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

        with self.assertRaises(ValueError):
            volume_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)

    def test_convert_nonnumeric_value(self):
        """Test exception is thrown for nonnumeric type."""
        with self.assertRaises(TypeError):
            volume_util.convert('a', VOLUME_GALLONS, VOLUME_LITERS)

    def test_convert_from_liters(self):
        """Test conversion from liters to other units."""
        liters = 5
        self.assertEqual(volume_util.convert(liters, VOLUME_LITERS,
                                             VOLUME_GALLONS), 1.321)

    def test_convert_from_gallons(self):
        """Test conversion from gallons to other units."""
        gallons = 5
        self.assertEqual(volume_util.convert(gallons, VOLUME_GALLONS,
                                             VOLUME_LITERS), 18.925)
