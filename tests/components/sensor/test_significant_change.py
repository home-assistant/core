"""Test the sensor significant change platform."""
from homeassistant.components.sensor.significant_change import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    async_check_significant_change,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)


async def test_significant_change_temperature():
    """Detect temperature significant changes."""
    celsius_attrs = {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
    }
    assert not async_check_significant_change(
        None, "12", celsius_attrs, "12", celsius_attrs
    )
    assert async_check_significant_change(
        None, "12", celsius_attrs, "13", celsius_attrs
    )
    assert not async_check_significant_change(
        None, "12.1", celsius_attrs, "12.2", celsius_attrs
    )

    freedom_attrs = {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT,
    }
    assert async_check_significant_change(
        None, "70", freedom_attrs, "71", freedom_attrs
    )
    assert not async_check_significant_change(
        None, "70", freedom_attrs, "70.5", freedom_attrs
    )


async def test_significant_change_battery():
    """Detect battery significant changes."""
    attrs = {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
    }
    assert not async_check_significant_change(None, "100", attrs, "100", attrs)
    assert async_check_significant_change(None, "100", attrs, "99", attrs)


async def test_significant_change_humidity():
    """Detect humidity significant changes."""
    attrs = {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
    }
    assert not async_check_significant_change(None, "100", attrs, "100", attrs)
    assert async_check_significant_change(None, "100", attrs, "99", attrs)
