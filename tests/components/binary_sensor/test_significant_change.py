"""Test the Binary Sensor significant change platform."""
from homeassistant.components.binary_sensor.significant_change import (
    async_check_significant_change,
)


async def test_significant_change():
    """Detect Binary Sensor significant changes."""
    old_attrs = {}
    new_attrs = {"a": 1}

    assert (
        async_check_significant_change(None, "on", old_attrs, "on", old_attrs) is False
    )
    assert (
        async_check_significant_change(None, "on", old_attrs, "off", old_attrs) is True
    )
    assert (
        async_check_significant_change(None, "on", old_attrs, "on", new_attrs) is False
    )
