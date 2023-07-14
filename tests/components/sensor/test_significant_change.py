"""Test the sensor significant change platform."""
import pytest

from homeassistant.components.sensor import SensorDeviceClass, significant_change
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)

AQI_ATTRS = {
    ATTR_DEVICE_CLASS: SensorDeviceClass.AQI,
}

BATTERY_ATTRS = {
    ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY,
}

HUMIDITY_ATTRS = {
    ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
}

TEMP_CELSIUS_ATTRS = {
    ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
}

TEMP_FREEDOM_ATTRS = {
    ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
}


@pytest.mark.parametrize(
    ("old_state", "new_state", "attrs", "result"),
    [
        ("0", "1", AQI_ATTRS, True),
        ("1", "0", AQI_ATTRS, True),
        ("0.1", "0.5", AQI_ATTRS, False),
        ("0.5", "0.1", AQI_ATTRS, False),
        ("99", "100", AQI_ATTRS, False),
        ("100", "99", AQI_ATTRS, False),
        ("101", "99", AQI_ATTRS, False),
        ("99", "101", AQI_ATTRS, True),
        ("100", "100", BATTERY_ATTRS, False),
        ("100", "99", BATTERY_ATTRS, True),
        ("100", "100", HUMIDITY_ATTRS, False),
        ("100", "99", HUMIDITY_ATTRS, True),
        ("12", "12", TEMP_CELSIUS_ATTRS, False),
        ("12", "13", TEMP_CELSIUS_ATTRS, True),
        ("12.1", "12.2", TEMP_CELSIUS_ATTRS, False),
        ("70", "71", TEMP_FREEDOM_ATTRS, True),
        ("70", "70.5", TEMP_FREEDOM_ATTRS, False),
        ("fail", "70", TEMP_FREEDOM_ATTRS, True),
        ("70", "fail", TEMP_FREEDOM_ATTRS, False),
    ],
)
async def test_significant_change_temperature(
    old_state, new_state, attrs, result
) -> None:
    """Detect temperature significant changes."""
    assert (
        significant_change.async_check_significant_change(
            None, old_state, attrs, new_state, attrs
        )
        is result
    )
