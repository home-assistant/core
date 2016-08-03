"""Test the unit system helper."""
import unittest

from homeassistant.helpers.unit_system import (
    UnitSystem,
    METRIC_SYSTEM,
    IMPERIAL_SYSTEM,
    TYPE_LENGTH,
    TYPE_TEMPERATURE,
    TYPE_MASS,
    TYPE_VOLUME,
)
from homeassistant.const import (
    LENGTH_METERS,
    LENGTH_KILOMETERS,
    MASS_GRAMS,
    VOLUME_LITERS,
    TEMP_CELSIUS,
)

SYSTEM_NAME = 'TEST'
INVALID_UNIT = 'INVALID'


class TestUnitSystem(unittest.TestCase):
    """Test the unit system helper."""

    def test_invalid_units(self):
        """Test errors are raised when invalid units are passed in."""
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

    def test_invalid_value(self):
        """Test no conversion happens if value is non-numeric."""
        self.assertEqual(('25a', LENGTH_KILOMETERS),
                         METRIC_SYSTEM.length('25a', LENGTH_KILOMETERS))
        self.assertEqual(('50K', TEMP_CELSIUS),
                         METRIC_SYSTEM.temperature('50K', TEMP_CELSIUS))

    def test_as_dict(self):
        """Test that the as_dict() method returns the expected dictionary."""
        expected = {
            TYPE_LENGTH: LENGTH_KILOMETERS,
            TYPE_TEMPERATURE: TEMP_CELSIUS,
            TYPE_VOLUME: VOLUME_LITERS,
            TYPE_MASS: MASS_GRAMS
        }

        self.assertEqual(expected, METRIC_SYSTEM.as_dict())

    def test_temperature_same_unit(self):
        """Test no conversion happens if to unit is same as from unit."""
        self.assertEqual(
            (5, METRIC_SYSTEM.temperature_unit),
            METRIC_SYSTEM.temperature(5,
                                      METRIC_SYSTEM.temperature_unit))

    def test_temperature_unknown_unit(self):
        """Test no conversion happens if unknown unit."""
        self.assertEqual((5, 'K'), METRIC_SYSTEM.temperature(5, 'K'))

    def test_temperature_to_metric(self):
        """Test temperature conversion to metric system."""
        self.assertEqual(
            (25, METRIC_SYSTEM.temperature_unit),
            METRIC_SYSTEM.temperature(25, METRIC_SYSTEM.temperature_unit))
        self.assertEqual(
            (26.7, TEMP_CELSIUS),
            METRIC_SYSTEM.temperature(80, IMPERIAL_SYSTEM.temperature_unit))

    def test_temperature_to_imperial(self):
        """Test temperature conversion to imperial system."""
        self.assertEqual(
            (77, IMPERIAL_SYSTEM.temperature_unit),
            IMPERIAL_SYSTEM.temperature(77, IMPERIAL_SYSTEM.temperature_unit))
        self.assertEqual(
            (77, IMPERIAL_SYSTEM.temperature_unit),
            IMPERIAL_SYSTEM.temperature(25, METRIC_SYSTEM.temperature_unit))

    def test_length_unknown_unit(self):
        """Test length conversion with unknown from unit."""
        self.assertEqual((5, 'fr'), METRIC_SYSTEM.length(5, 'fr'))

    def test_length_to_metric(self):
        """Test length conversion to metric system."""
        self.assertEqual(
            (100, METRIC_SYSTEM.length_unit),
            METRIC_SYSTEM.length(100, METRIC_SYSTEM.length_unit)
        )
        self.assertEqual(
            (8.04672, METRIC_SYSTEM.length_unit),
            METRIC_SYSTEM.length(5, IMPERIAL_SYSTEM.length_unit)
        )

    def test_length_to_imperial(self):
        """Test length conversion to imperial system."""
        self.assertEqual(
            (100, IMPERIAL_SYSTEM.length_unit),
            IMPERIAL_SYSTEM.length(100,
                                   IMPERIAL_SYSTEM.length_unit)
        )
        self.assertEqual(
            (3.106855, IMPERIAL_SYSTEM.length_unit),
            IMPERIAL_SYSTEM.length(5, METRIC_SYSTEM.length_unit)
        )

    def test_properties(self):
        """Test the unit properties are returned as expected."""
        self.assertEqual(LENGTH_KILOMETERS, METRIC_SYSTEM.length_unit)
        self.assertEqual(TEMP_CELSIUS, METRIC_SYSTEM.temperature_unit)
        self.assertEqual(MASS_GRAMS, METRIC_SYSTEM.mass_unit)
        self.assertEqual(VOLUME_LITERS, METRIC_SYSTEM.volume_unit)

    def test_is_metric(self):
        """Test the is metric flag."""
        self.assertTrue(METRIC_SYSTEM.is_metric)
        self.assertFalse(IMPERIAL_SYSTEM.is_metric)
