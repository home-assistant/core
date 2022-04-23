"""The tests for the Daikin target temperature conversion."""
from homeassistant.components.daikin.climate import format_target_temperature


def test_int_conversion():
    """Check no decimal are kept when target temp is an integer."""
    formatted = format_target_temperature("16")
    assert formatted == "16"


def test_decimal_conversion():
    """Check 1 decimal is kept when target temp is a decimal."""
    formatted = format_target_temperature("16.1")
    assert formatted == "16.1"


def test_decimal_conversion_more_digits():
    """Check at most 1 decimal is kept when target temp is a decimal with more than 1 decimal."""
    formatted = format_target_temperature("16.09")
    assert formatted == "16.1"
