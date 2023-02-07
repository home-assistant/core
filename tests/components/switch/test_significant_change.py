"""Test the sensor significant change platform."""
from homeassistant.components.switch.significant_change import (
    async_check_significant_change,
)


async def test_significant_change() -> None:
    """Detect Switch significant change."""
    attrs = {}
    assert not async_check_significant_change(None, "on", attrs, "on", attrs)
    assert not async_check_significant_change(None, "off", attrs, "off", attrs)
    assert async_check_significant_change(None, "on", attrs, "off", attrs)
