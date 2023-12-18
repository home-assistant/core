"""Test the Water Heater significant change platform."""
import pytest

from homeassistant.components.water_heater import (
    ATTR_AWAY_MODE,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_OPERATION_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
)
from homeassistant.components.water_heater.significant_change import (
    async_check_significant_change,
)


async def test_significant_state_change() -> None:
    """Detect Water Heater significant state changes."""
    attrs = {}
    assert not async_check_significant_change(None, "on", attrs, "on", attrs)
    assert async_check_significant_change(None, "on", attrs, "off", attrs)


@pytest.mark.parametrize(
    ("old_attrs", "new_attrs", "expected_result"),
    [
        ({ATTR_AWAY_MODE: "old_value"}, {ATTR_AWAY_MODE: "old_value"}, False),
        ({ATTR_AWAY_MODE: "old_value"}, {ATTR_AWAY_MODE: "new_value"}, True),
        ({ATTR_OPERATION_MODE: "old_value"}, {ATTR_OPERATION_MODE: "new_value"}, True),
        # multiple attributes
        (
            {ATTR_AWAY_MODE: "old_value", ATTR_OPERATION_MODE: "old_value"},
            {ATTR_AWAY_MODE: "new_value", ATTR_OPERATION_MODE: "old_value"},
            True,
        ),
        # float attributes
        ({ATTR_CURRENT_TEMPERATURE: 50.0}, {ATTR_CURRENT_TEMPERATURE: 50.5}, True),
        ({ATTR_CURRENT_TEMPERATURE: 50.0}, {ATTR_CURRENT_TEMPERATURE: 50.4}, False),
        ({ATTR_CURRENT_TEMPERATURE: "invalid"}, {ATTR_CURRENT_TEMPERATURE: 10.0}, True),
        (
            {ATTR_CURRENT_TEMPERATURE: 10.0},
            {ATTR_CURRENT_TEMPERATURE: "invalid"},
            False,
        ),
        ({ATTR_TEMPERATURE: 70.0}, {ATTR_TEMPERATURE: 70.5}, True),
        ({ATTR_TEMPERATURE: 70.0}, {ATTR_TEMPERATURE: 70.4}, False),
        ({ATTR_TARGET_TEMP_HIGH: 80.0}, {ATTR_TARGET_TEMP_HIGH: 80.5}, True),
        ({ATTR_TARGET_TEMP_HIGH: 80.0}, {ATTR_TARGET_TEMP_HIGH: 80.4}, False),
        ({ATTR_TARGET_TEMP_LOW: 30.0}, {ATTR_TARGET_TEMP_LOW: 30.5}, True),
        ({ATTR_TARGET_TEMP_LOW: 30.0}, {ATTR_TARGET_TEMP_LOW: 30.4}, False),
        # insignificant attributes
        ({"unknown_attr": "old_value"}, {"unknown_attr": "old_value"}, False),
        ({"unknown_attr": "old_value"}, {"unknown_attr": "new_value"}, False),
    ],
)
async def test_significant_atributes_change(
    old_attrs: dict, new_attrs: dict, expected_result: bool
) -> None:
    """Detect Water Heater significant attribute changes."""
    assert (
        async_check_significant_change(None, "state", old_attrs, "state", new_attrs)
        == expected_result
    )
