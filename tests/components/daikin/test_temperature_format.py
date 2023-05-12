"""The tests for the Daikin target temperature conversion."""
from homeassistant.components.daikin.climate import format_target_temperature


def test_int_conversion() -> None:
    """Check no decimal are kept when target temp is an integer."""
    formatted = format_target_temperature("16")
    assert formatted == "16"


def test_rounding() -> None:
    """Check 1 decimal is kept when target temp is a decimal."""
    formatted = format_target_temperature("16.1")
    assert formatted == "16"
    formatted = format_target_temperature("16.3")
    assert formatted == "16.5"
    formatted = format_target_temperature("16.65")
    assert formatted == "16.5"
    formatted = format_target_temperature("16.9")
    assert formatted == "17"
