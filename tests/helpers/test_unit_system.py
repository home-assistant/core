"""Test the unit system helper."""
import unittest

from homeassistant.helpers.unit_system import (UnitSystem)
from homeassistant.const import (
    LENGTH_METERS, MASS_GRAMS, VOLUME_LITERS, TEMP_CELSIUS)

SYSTEM_NAME = 'TEST'
INVALID_UNIT = 'INVALID'


class TestUnitSystem(unittest.TestCase):
    """Test the unit system helper."""

    def test_invalid_units(self):
        with self.assertRaises(ValueError):
            UnitSystem(SYSTEM_NAME, INVALID_UNIT, LENGTH_METERS, VOLUME_LITERS,
                       MASS_GRAMS)

        with self.assertRaises(ValueError):
            UnitSystem(SYSTEM_NAME, TEMP_CELSIUS, INVALID_UNIT, VOLUME_LITERS,
                       MASS_GRAMS)

        with self.assertRaises(ValueError):
            UnitSystem(SYSTEM_NAME, TEMP_CELSIUS, LENGTH_METERS, INVALID_UNIT,
                       MASS_GRAMS)

        with self.assertRaises(ValueError):
            UnitSystem(SYSTEM_NAME, TEMP_CELSIUS, LENGTH_METERS, VOLUME_LITERS,
                       INVALID_UNIT)
