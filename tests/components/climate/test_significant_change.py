"""Test the Climate significant change platform."""

import pytest

from homeassistant.components.climate import (
    ATTR_AUX_HEAT,
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
)
from homeassistant.components.climate.significant_change import (
    async_check_significant_change,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import (
    METRIC_SYSTEM as METRIC,
    US_CUSTOMARY_SYSTEM as IMPERIAL,
    UnitSystem,
)


async def test_significant_state_change(hass: HomeAssistant) -> None:
    """Detect Climate significant state_changes."""
    attrs = {}
    assert not async_check_significant_change(hass, "on", attrs, "on", attrs)
    assert async_check_significant_change(hass, "on", attrs, "off", attrs)


@pytest.mark.parametrize(
    ("unit_system", "old_attrs", "new_attrs", "expected_result"),
    [
        (METRIC, {ATTR_AUX_HEAT: "old_value"}, {ATTR_AUX_HEAT: "old_value"}, False),
        (METRIC, {ATTR_AUX_HEAT: "old_value"}, {ATTR_AUX_HEAT: "new_value"}, True),
        (METRIC, {ATTR_FAN_MODE: "old_value"}, {ATTR_FAN_MODE: "old_value"}, False),
        (METRIC, {ATTR_FAN_MODE: "old_value"}, {ATTR_FAN_MODE: "new_value"}, True),
        (
            METRIC,
            {ATTR_HVAC_ACTION: "old_value"},
            {ATTR_HVAC_ACTION: "old_value"},
            False,
        ),
        (
            METRIC,
            {ATTR_HVAC_ACTION: "old_value"},
            {ATTR_HVAC_ACTION: "new_value"},
            True,
        ),
        (
            METRIC,
            {ATTR_PRESET_MODE: "old_value"},
            {ATTR_PRESET_MODE: "old_value"},
            False,
        ),
        (
            METRIC,
            {ATTR_PRESET_MODE: "old_value"},
            {ATTR_PRESET_MODE: "new_value"},
            True,
        ),
        (METRIC, {ATTR_SWING_MODE: "old_value"}, {ATTR_SWING_MODE: "old_value"}, False),
        (METRIC, {ATTR_SWING_MODE: "old_value"}, {ATTR_SWING_MODE: "new_value"}, True),
        (
            METRIC,
            {ATTR_SWING_HORIZONTAL_MODE: "old_value"},
            {ATTR_SWING_HORIZONTAL_MODE: "old_value"},
            False,
        ),
        (
            METRIC,
            {ATTR_SWING_HORIZONTAL_MODE: "old_value"},
            {ATTR_SWING_HORIZONTAL_MODE: "new_value"},
            True,
        ),
        # multiple attributes
        (
            METRIC,
            {ATTR_HVAC_ACTION: "old_value", ATTR_PRESET_MODE: "old_value"},
            {ATTR_HVAC_ACTION: "new_value", ATTR_PRESET_MODE: "old_value"},
            True,
        ),
        # float attributes
        (METRIC, {ATTR_CURRENT_HUMIDITY: 60.0}, {ATTR_CURRENT_HUMIDITY: 61}, True),
        (METRIC, {ATTR_CURRENT_HUMIDITY: 60.0}, {ATTR_CURRENT_HUMIDITY: 60.9}, False),
        (
            METRIC,
            {ATTR_CURRENT_HUMIDITY: "invalid"},
            {ATTR_CURRENT_HUMIDITY: 60.0},
            True,
        ),
        (
            METRIC,
            {ATTR_CURRENT_HUMIDITY: 60.0},
            {ATTR_CURRENT_HUMIDITY: "invalid"},
            False,
        ),
        (
            METRIC,
            {ATTR_CURRENT_TEMPERATURE: 22.0},
            {ATTR_CURRENT_TEMPERATURE: 22.5},
            True,
        ),
        (
            METRIC,
            {ATTR_CURRENT_TEMPERATURE: 22.0},
            {ATTR_CURRENT_TEMPERATURE: 22.4},
            False,
        ),
        (METRIC, {ATTR_HUMIDITY: 60.0}, {ATTR_HUMIDITY: 61.0}, True),
        (METRIC, {ATTR_HUMIDITY: 60.0}, {ATTR_HUMIDITY: 60.9}, False),
        (METRIC, {ATTR_TARGET_TEMP_HIGH: 31.0}, {ATTR_TARGET_TEMP_HIGH: 31.5}, True),
        (METRIC, {ATTR_TARGET_TEMP_HIGH: 31.0}, {ATTR_TARGET_TEMP_HIGH: 31.4}, False),
        (METRIC, {ATTR_TARGET_TEMP_LOW: 8.0}, {ATTR_TARGET_TEMP_LOW: 8.5}, True),
        (METRIC, {ATTR_TARGET_TEMP_LOW: 8.0}, {ATTR_TARGET_TEMP_LOW: 8.4}, False),
        (METRIC, {ATTR_TEMPERATURE: 22.0}, {ATTR_TEMPERATURE: 22.5}, True),
        (METRIC, {ATTR_TEMPERATURE: 22.0}, {ATTR_TEMPERATURE: 22.4}, False),
        (IMPERIAL, {ATTR_TEMPERATURE: 70.0}, {ATTR_TEMPERATURE: 71.0}, True),
        (IMPERIAL, {ATTR_TEMPERATURE: 70.0}, {ATTR_TEMPERATURE: 70.9}, False),
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
    """Detect Climate significant attribute changes."""
    hass.config.units = unit_system
    assert (
        async_check_significant_change(hass, "state", old_attrs, "state", new_attrs)
        == expected_result
    )
