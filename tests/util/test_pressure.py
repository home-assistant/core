"""Test homeassistant pressure utility functions."""
import unittest
import pytest

from homeassistant.const import (PRESSURE_PA, PRESSURE_HPA, PRESSURE_MBAR,
                                 PRESSURE_INHG, PRESSURE_PSI)
import homeassistant.util.pressure as pressure_util

INVALID_SYMBOL = 'bob'
VALID_SYMBOL = PRESSURE_PA


class TestPressureUtil(unittest.TestCase):
    """Test the pressure utility functions."""

    def test_convert_same_unit(self):
        """Test conversion from any unit to same unit."""
        assert pressure_util.convert(2, PRESSURE_PA, PRESSURE_PA) == 2
        assert pressure_util.convert(3, PRESSURE_HPA, PRESSURE_HPA) == 3
        assert pressure_util.convert(4, PRESSURE_MBAR, PRESSURE_MBAR) == 4
        assert pressure_util.convert(5, PRESSURE_INHG, PRESSURE_INHG) == 5

    def test_convert_invalid_unit(self):
        """Test exception is thrown for invalid units."""
        with pytest.raises(ValueError):
            pressure_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

        with pytest.raises(ValueError):
            pressure_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)

    def test_convert_nonnumeric_value(self):
        """Test exception is thrown for nonnumeric type."""
        with pytest.raises(TypeError):
            pressure_util.convert('a', PRESSURE_HPA, PRESSURE_INHG)

    def test_convert_from_hpascals(self):
        """Test conversion from hPA to other units."""
        hpascals = 1000
        self.assertAlmostEqual(
            pressure_util.convert(hpascals, PRESSURE_HPA, PRESSURE_PSI),
            14.5037743897)
        self.assertAlmostEqual(
            pressure_util.convert(hpascals, PRESSURE_HPA, PRESSURE_INHG),
            29.5299801647)
        self.assertAlmostEqual(
            pressure_util.convert(hpascals, PRESSURE_HPA, PRESSURE_PA),
            100000)
        self.assertAlmostEqual(
            pressure_util.convert(hpascals, PRESSURE_HPA, PRESSURE_MBAR),
            1000)

    def test_convert_from_inhg(self):
        """Test conversion from inHg to other units."""
        inhg = 30
        self.assertAlmostEqual(
            pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_PSI),
            14.7346266155)
        self.assertAlmostEqual(
            pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_HPA),
            1015.9167)
        self.assertAlmostEqual(
            pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_PA),
            101591.67)
        self.assertAlmostEqual(
            pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_MBAR),
            1015.9167)
