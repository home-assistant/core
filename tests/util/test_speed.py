"""Test Home Assistant speed utility functions."""
import pytest

from homeassistant.const import (
    SPEED_INCHES_PER_DAY,
    SPEED_INCHES_PER_HOUR,
    SPEED_MILLIMETERS_PER_DAY,
    UnitOfSpeed,
)
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.speed as speed_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = UnitOfSpeed.KILOMETERS_PER_HOUR


def test_raise_deprecation_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Ensure that a warning is raised on use of convert."""
    assert speed_util.convert(2, SPEED_INCHES_PER_DAY, SPEED_INCHES_PER_DAY) == 2
    assert "use unit_conversion.SpeedConverter instead" in caplog.text


def test_convert_same_unit() -> None:
    """Test conversion from any unit to same unit."""
    assert speed_util.convert(2, SPEED_INCHES_PER_DAY, SPEED_INCHES_PER_DAY) == 2
    assert speed_util.convert(3, SPEED_INCHES_PER_HOUR, SPEED_INCHES_PER_HOUR) == 3
    assert (
        speed_util.convert(
            4, UnitOfSpeed.KILOMETERS_PER_HOUR, UnitOfSpeed.KILOMETERS_PER_HOUR
        )
        == 4
    )
    assert (
        speed_util.convert(
            5, UnitOfSpeed.METERS_PER_SECOND, UnitOfSpeed.METERS_PER_SECOND
        )
        == 5
    )
    assert (
        speed_util.convert(6, UnitOfSpeed.MILES_PER_HOUR, UnitOfSpeed.MILES_PER_HOUR)
        == 6
    )
    assert (
        speed_util.convert(7, SPEED_MILLIMETERS_PER_DAY, SPEED_MILLIMETERS_PER_DAY) == 7
    )


def test_convert_invalid_unit() -> None:
    """Test exception is thrown for invalid units."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        speed_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        speed_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value() -> None:
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        speed_util.convert(
            "a", UnitOfSpeed.KILOMETERS_PER_HOUR, UnitOfSpeed.MILES_PER_HOUR
        )


@pytest.mark.parametrize(
    ("from_value", "from_unit", "expected", "to_unit"),
    [
        # 5 km/h / 1.609 km/mi = 3.10686 mi/h
        (5, UnitOfSpeed.KILOMETERS_PER_HOUR, 3.10686, UnitOfSpeed.MILES_PER_HOUR),
        # 5 mi/h * 1.609 km/mi = 8.04672 km/h
        (5, UnitOfSpeed.MILES_PER_HOUR, 8.04672, UnitOfSpeed.KILOMETERS_PER_HOUR),
        # 5 in/day * 25.4 mm/in = 127 mm/day
        (5, SPEED_INCHES_PER_DAY, 127, SPEED_MILLIMETERS_PER_DAY),
        # 5 mm/day / 25.4 mm/in = 0.19685 in/day
        (5, SPEED_MILLIMETERS_PER_DAY, 0.19685, SPEED_INCHES_PER_DAY),
        # 5 in/hr * 24 hr/day = 3048 mm/day
        (5, SPEED_INCHES_PER_HOUR, 3048, SPEED_MILLIMETERS_PER_DAY),
        # 5 m/s * 39.3701 in/m * 3600 s/hr = 708661
        (5, UnitOfSpeed.METERS_PER_SECOND, 708661, SPEED_INCHES_PER_HOUR),
        # 5000 in/h / 39.3701 in/m / 3600 s/h = 0.03528 m/s
        (5000, SPEED_INCHES_PER_HOUR, 0.03528, UnitOfSpeed.METERS_PER_SECOND),
        # 5 kt * 1852 m/nmi / 3600 s/h = 2.5722 m/s
        (5, UnitOfSpeed.KNOTS, 2.5722, UnitOfSpeed.METERS_PER_SECOND),
        # 5 ft/s * 0.3048 m/ft = 1.524 m/s
        (5, UnitOfSpeed.FEET_PER_SECOND, 1.524, UnitOfSpeed.METERS_PER_SECOND),
    ],
)
def test_convert_different_units(from_value, from_unit, expected, to_unit) -> None:
    """Test conversion between units."""
    assert speed_util.convert(from_value, from_unit, to_unit) == pytest.approx(
        expected, rel=1e-4
    )
