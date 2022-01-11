"""Tradfri utility function tests."""

from homeassistant.components.tradfri.fan import _from_fan_percentage, _from_fan_speed


def test_from_fan_speed():
    """Test that we can convert fan speed to percentage value."""
    assert _from_fan_speed(41) == 84


def test_from_percentage():
    """Test that we can convert percentage value to fan speed."""
    assert _from_fan_percentage(84) == 41


def test_from_percentage_limit():
    """
    Test that we can convert percentage value to fan speed.

    Handle special case of percent value being below 20.
    """
    assert _from_fan_percentage(2) == 1
