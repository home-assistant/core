"""Test the unit system helper."""
import unittest

from homeassistant.util.unit_system import (
    UnitSystem,
    METRIC_SYSTEM,
    IMPERIAL_SYSTEM,
)
from homeassistant.const import (
    LENGTH_METERS,
    LENGTH_KILOMETERS,
    MASS_GRAMS,
    VOLUME_LITERS,
    TEMP_CELSIUS,
    LENGTH,
    MASS,
    TEMPERATURE,
    VOLUME
)
import pytest

SYSTEM_NAME = 'TEST'
INVALID_UNIT = 'INVALID'


class TestUnitSystem(unittest.TestCase):
    """Test the unit system helper."""

    def test_invalid_units(self):
        """Test errors are raised when invalid units are passed in."""
        with pytest.raises(ValueError):
            UnitSystem(SYSTEM_NAME, INVALID_UNIT, LENGTH_METERS, VOLUME_LITERS,
                       MASS_GRAMS)

        with pytest.raises(ValueError):
            UnitSystem(SYSTEM_NAME, TEMP_CELSIUS, INVALID_UNIT, VOLUME_LITERS,
                       MASS_GRAMS)

        with pytest.raises(ValueError):
            UnitSystem(SYSTEM_NAME, TEMP_CELSIUS, LENGTH_METERS, INVALID_UNIT,
                       MASS_GRAMS)

        with pytest.raises(ValueError):
            UnitSystem(SYSTEM_NAME, TEMP_CELSIUS, LENGTH_METERS, VOLUME_LITERS,
                       INVALID_UNIT)

    def test_invalid_value(self):
        """Test no conversion happens if value is non-numeric."""
        with pytest.raises(TypeError):
            METRIC_SYSTEM.length('25a', LENGTH_KILOMETERS)
        with pytest.raises(TypeError):
            METRIC_SYSTEM.temperature('50K', TEMP_CELSIUS)

    def test_as_dict(self):
        """Test that the as_dict() method returns the expected dictionary."""
        expected = {
            LENGTH: LENGTH_KILOMETERS,
            TEMPERATURE: TEMP_CELSIUS,
            VOLUME: VOLUME_LITERS,
            MASS: MASS_GRAMS
        }

        assert expected == METRIC_SYSTEM.as_dict()

    def test_temperature_same_unit(self):
        """Test no conversion happens if to unit is same as from unit."""
        assert 5 == \
            METRIC_SYSTEM.temperature(5,
                                      METRIC_SYSTEM.temperature_unit)

    def test_temperature_unknown_unit(self):
        """Test no conversion happens if unknown unit."""
        with pytest.raises(ValueError):
            METRIC_SYSTEM.temperature(5, 'K')

    def test_temperature_to_metric(self):
        """Test temperature conversion to metric system."""
        assert 25 == \
            METRIC_SYSTEM.temperature(25, METRIC_SYSTEM.temperature_unit)
        assert 26.7 == \
            round(METRIC_SYSTEM.temperature(
                80, IMPERIAL_SYSTEM.temperature_unit), 1)

    def test_temperature_to_imperial(self):
        """Test temperature conversion to imperial system."""
        assert 77 == \
            IMPERIAL_SYSTEM.temperature(77, IMPERIAL_SYSTEM.temperature_unit)
        assert 77 == \
            IMPERIAL_SYSTEM.temperature(25, METRIC_SYSTEM.temperature_unit)

    def test_length_unknown_unit(self):
        """Test length conversion with unknown from unit."""
        with pytest.raises(ValueError):
            METRIC_SYSTEM.length(5, 'fr')

    def test_length_to_metric(self):
        """Test length conversion to metric system."""
        assert 100 == \
            METRIC_SYSTEM.length(100, METRIC_SYSTEM.length_unit)
        assert 8.04672 == \
            METRIC_SYSTEM.length(5, IMPERIAL_SYSTEM.length_unit)

    def test_length_to_imperial(self):
        """Test length conversion to imperial system."""
        assert 100 == \
            IMPERIAL_SYSTEM.length(100,
                                   IMPERIAL_SYSTEM.length_unit)
        assert 3.106855 == \
            IMPERIAL_SYSTEM.length(5, METRIC_SYSTEM.length_unit)

    def test_properties(self):
        """Test the unit properties are returned as expected."""
        assert LENGTH_KILOMETERS == METRIC_SYSTEM.length_unit
        assert TEMP_CELSIUS == METRIC_SYSTEM.temperature_unit
        assert MASS_GRAMS == METRIC_SYSTEM.mass_unit
        assert VOLUME_LITERS == METRIC_SYSTEM.volume_unit

    def test_is_metric(self):
        """Test the is metric flag."""
        assert METRIC_SYSTEM.is_metric
        assert not IMPERIAL_SYSTEM.is_metric
