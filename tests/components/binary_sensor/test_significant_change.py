"""Test the Binary Sensor significant change platform."""

from homeassistant.components.binary_sensor.significant_change import (
    async_check_significant_change,
)


async def test_significant_change() -> None:
    """Detect Binary Sensor significant changes."""
    old_attrs = {"attr_1": "value_1"}
    new_attrs = {"attr_1": "value_2"}

    assert (
        async_check_significant_change(None, "on", old_attrs, "on", old_attrs) is False
    )
    assert (
        async_check_significant_change(None, "on", old_attrs, "on", new_attrs) is False
    )
    assert (
        async_check_significant_change(None, "on", old_attrs, "off", old_attrs) is True
    )
