"""Test the Number significant change platform."""
import pytest

from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.number.significant_change import (
    async_check_significant_change,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfTemperature,
)

AQI_ATTRS = {ATTR_DEVICE_CLASS: NumberDeviceClass.AQI}
BATTERY_ATTRS = {ATTR_DEVICE_CLASS: NumberDeviceClass.BATTERY}
CO_ATTRS = {ATTR_DEVICE_CLASS: NumberDeviceClass.CO}
CO2_ATTRS = {ATTR_DEVICE_CLASS: NumberDeviceClass.CO2}
HUMIDITY_ATTRS = {ATTR_DEVICE_CLASS: NumberDeviceClass.HUMIDITY}
MOISTURE_ATTRS = {ATTR_DEVICE_CLASS: NumberDeviceClass.MOISTURE}
PM1_ATTRS = {ATTR_DEVICE_CLASS: NumberDeviceClass.PM1}
PM10_ATTRS = {ATTR_DEVICE_CLASS: NumberDeviceClass.PM10}
PM25_ATTRS = {ATTR_DEVICE_CLASS: NumberDeviceClass.PM25}
POWER_FACTOR_ATTRS = {
    ATTR_DEVICE_CLASS: NumberDeviceClass.POWER_FACTOR,
}
POWER_FACTOR_ATTRS_PERCENTAGE = {
    ATTR_DEVICE_CLASS: NumberDeviceClass.POWER_FACTOR,
    ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
}
TEMP_CELSIUS_ATTRS = {
    ATTR_DEVICE_CLASS: NumberDeviceClass.TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
}
TEMP_FREEDOM_ATTRS = {
    ATTR_DEVICE_CLASS: NumberDeviceClass.TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
}
VOLATILE_ORGANIC_COMPOUNDS_ATTRS = {
    ATTR_DEVICE_CLASS: NumberDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
}


@pytest.mark.parametrize(
    ("old_state", "new_state", "attrs", "result"),
    [
        ("0", "0.9", {}, None),
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
        ("0", "1", CO_ATTRS, True),
        ("0.1", "0.5", CO_ATTRS, False),
        ("0", "1", CO2_ATTRS, True),
        ("0.1", "0.5", CO2_ATTRS, False),
        ("100", "100", HUMIDITY_ATTRS, False),
        ("100", "99", HUMIDITY_ATTRS, True),
        ("100", "100", MOISTURE_ATTRS, False),
        ("100", "99", MOISTURE_ATTRS, True),
        ("0", "1", PM1_ATTRS, True),
        ("0.1", "0.5", PM1_ATTRS, False),
        ("0", "1", PM10_ATTRS, True),
        ("0.1", "0.5", PM10_ATTRS, False),
        ("0", "1", PM25_ATTRS, True),
        ("0.1", "0.5", PM25_ATTRS, False),
        ("0.1", "0.2", POWER_FACTOR_ATTRS, True),
        ("0.1", "0.19", POWER_FACTOR_ATTRS, False),
        ("1", "2", POWER_FACTOR_ATTRS_PERCENTAGE, True),
        ("1", "1.9", POWER_FACTOR_ATTRS_PERCENTAGE, False),
        ("12", "12", TEMP_CELSIUS_ATTRS, False),
        ("12", "13", TEMP_CELSIUS_ATTRS, True),
        ("12.1", "12.2", TEMP_CELSIUS_ATTRS, False),
        ("70", "71", TEMP_FREEDOM_ATTRS, True),
        ("70", "70.5", TEMP_FREEDOM_ATTRS, False),
        ("fail", "70", TEMP_FREEDOM_ATTRS, True),
        ("70", "fail", TEMP_FREEDOM_ATTRS, False),
        ("0", "1", VOLATILE_ORGANIC_COMPOUNDS_ATTRS, True),
        ("0.1", "0.5", VOLATILE_ORGANIC_COMPOUNDS_ATTRS, False),
    ],
)
async def test_significant_change_temperature(
    old_state, new_state, attrs, result
) -> None:
    """Detect temperature significant changes."""
    assert (
        async_check_significant_change(None, old_state, attrs, new_state, attrs)
        is result
    )
