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
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import (
    METRIC_SYSTEM as METRIC,
    US_CUSTOMARY_SYSTEM as IMPERIAL,
    UnitSystem,
)


async def test_significant_state_change(hass: HomeAssistant) -> None:
    """Detect Water Heater significant state changes."""
    attrs = {}
    assert not async_check_significant_change(hass, "on", attrs, "on", attrs)
    assert async_check_significant_change(hass, "on", attrs, "off", attrs)


@pytest.mark.parametrize(
    ("unit_system", "old_attrs", "new_attrs", "expected_result"),
    [
        (METRIC, {ATTR_AWAY_MODE: "old_value"}, {ATTR_AWAY_MODE: "old_value"}, False),
        (METRIC, {ATTR_AWAY_MODE: "old_value"}, {ATTR_AWAY_MODE: "new_value"}, True),
        (
            METRIC,
            {ATTR_OPERATION_MODE: "old_value"},
            {ATTR_OPERATION_MODE: "new_value"},
            True,
        ),
        # multiple attributes
        (
            METRIC,
            {ATTR_AWAY_MODE: "old_value", ATTR_OPERATION_MODE: "old_value"},
            {ATTR_AWAY_MODE: "new_value", ATTR_OPERATION_MODE: "old_value"},
            True,
        ),
        # float attributes
        (
            METRIC,
            {ATTR_CURRENT_TEMPERATURE: 50.0},
            {ATTR_CURRENT_TEMPERATURE: 50.5},
            True,
        ),
        (
            METRIC,
            {ATTR_CURRENT_TEMPERATURE: 50.0},
            {ATTR_CURRENT_TEMPERATURE: 50.4},
            False,
        ),
        (
            METRIC,
            {ATTR_CURRENT_TEMPERATURE: "invalid"},
            {ATTR_CURRENT_TEMPERATURE: 10.0},
            True,
        ),
        (
            METRIC,
            {ATTR_CURRENT_TEMPERATURE: 10.0},
            {ATTR_CURRENT_TEMPERATURE: "invalid"},
            False,
        ),
        (IMPERIAL, {ATTR_TEMPERATURE: 160.0}, {ATTR_TEMPERATURE: 161}, True),
        (IMPERIAL, {ATTR_TEMPERATURE: 160.0}, {ATTR_TEMPERATURE: 160.9}, False),
        (METRIC, {ATTR_TARGET_TEMP_HIGH: 80.0}, {ATTR_TARGET_TEMP_HIGH: 80.5}, True),
        (METRIC, {ATTR_TARGET_TEMP_HIGH: 80.0}, {ATTR_TARGET_TEMP_HIGH: 80.4}, False),
        (METRIC, {ATTR_TARGET_TEMP_LOW: 30.0}, {ATTR_TARGET_TEMP_LOW: 30.5}, True),
        (METRIC, {ATTR_TARGET_TEMP_LOW: 30.0}, {ATTR_TARGET_TEMP_LOW: 30.4}, False),
        # insignificant attributes
        (METRIC, {"unknown_attr": "old_value"}, {"unknown_attr": "old_value"}, False),
        (METRIC, {"unknown_attr": "old_value"}, {"unknown_attr": "new_value"}, False),
    ],
)
async def test_significant_atributes_change(
    hass: HomeAssistant,
    unit_system: UnitSystem,
    old_attrs: dict,
    new_attrs: dict,
    expected_result: bool,
) -> None:
    """Detect Water Heater significant attribute changes."""
    hass.config.units = unit_system
    assert (
        async_check_significant_change(hass, "state", old_attrs, "state", new_attrs)
        == expected_result
    )
