"""Tradfri utility function tests."""
import pytest

from homeassistant.components.tradfri.fan import _from_fan_percentage, _from_fan_speed


@pytest.mark.parametrize(
    "fan_speed, expected_result",
    [
        (0, 0),
        (2, 2),
        (25, 49),
        (50, 100),
    ],
)
def test_from_fan_speed(fan_speed, expected_result):
    """Test that we can convert fan speed to percentage value."""
    assert _from_fan_speed(fan_speed) == expected_result


@pytest.mark.parametrize(
    "percentage, expected_result",
    [
        (1, 2),
        (100, 50),
        (50, 26),
    ],
)
def test_from_percentage(percentage, expected_result):
    """Test that we can convert percentage value to fan speed."""
    assert _from_fan_percentage(percentage) == expected_result
