"""Test the sensor significant change platform."""
from homeassistant.components.NEW_DOMAIN.significant_change import (
    async_check_significant_change,
)
from homeassistant.const import ATTR_DEVICE_CLASS


async def test_significant_change():
    """Detect NEW_NAME significant change."""
    attrs = {ATTR_DEVICE_CLASS: "some_device_class"}

    assert not async_check_significant_change(None, "on", attrs, "on", attrs)

    assert async_check_significant_change(None, "on", attrs, "off", attrs)
