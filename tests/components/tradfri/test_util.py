"""Tradfri utility function tests."""

from homeassistant.components.tradfri.fan import _from_fan_speed, _from_percentage


def test_from_fan_speed():
    """Test that we can convert fan speed to percentage value."""
    assert _from_fan_speed(40) == 80


def test_from_percentage():
    """Test that we can convert percentage value to fan speed."""
    assert _from_percentage(80) == 40
