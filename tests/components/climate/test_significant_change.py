"""Test the Climate significant change platform."""

import pytest

from homeassistant.components.climate import ClimateEntityStateAttribute
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
        (
            METRIC,
            {ClimateEntityStateAttribute.FAN_MODE: "old_value"},
            {ClimateEntityStateAttribute.FAN_MODE: "old_value"},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.FAN_MODE: "old_value"},
            {ClimateEntityStateAttribute.FAN_MODE: "new_value"},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.HVAC_ACTION: "old_value"},
            {ClimateEntityStateAttribute.HVAC_ACTION: "old_value"},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.HVAC_ACTION: "old_value"},
            {ClimateEntityStateAttribute.HVAC_ACTION: "new_value"},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.PRESET_MODE: "old_value"},
            {ClimateEntityStateAttribute.PRESET_MODE: "old_value"},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.PRESET_MODE: "old_value"},
            {ClimateEntityStateAttribute.PRESET_MODE: "new_value"},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.SWING_MODE: "old_value"},
            {ClimateEntityStateAttribute.SWING_MODE: "old_value"},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.SWING_MODE: "old_value"},
            {ClimateEntityStateAttribute.SWING_MODE: "new_value"},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE: "old_value"},
            {ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE: "old_value"},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE: "old_value"},
            {ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE: "new_value"},
            True,
        ),
        # multiple attributes
        (
            METRIC,
            {
                ClimateEntityStateAttribute.HVAC_ACTION: "old_value",
                ClimateEntityStateAttribute.PRESET_MODE: "old_value",
            },
            {
                ClimateEntityStateAttribute.HVAC_ACTION: "new_value",
                ClimateEntityStateAttribute.PRESET_MODE: "old_value",
            },
            True,
        ),
        # float attributes
        (
            METRIC,
            {ClimateEntityStateAttribute.CURRENT_HUMIDITY: 60.0},
            {ClimateEntityStateAttribute.CURRENT_HUMIDITY: 61},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.CURRENT_HUMIDITY: 60.0},
            {ClimateEntityStateAttribute.CURRENT_HUMIDITY: 60.9},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.CURRENT_HUMIDITY: "invalid"},
            {ClimateEntityStateAttribute.CURRENT_HUMIDITY: 60.0},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.CURRENT_HUMIDITY: 60.0},
            {ClimateEntityStateAttribute.CURRENT_HUMIDITY: "invalid"},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.CURRENT_TEMPERATURE: 22.0},
            {ClimateEntityStateAttribute.CURRENT_TEMPERATURE: 22.5},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.CURRENT_TEMPERATURE: 22.0},
            {ClimateEntityStateAttribute.CURRENT_TEMPERATURE: 22.4},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.TARGET_HUMIDITY: 60.0},
            {ClimateEntityStateAttribute.TARGET_HUMIDITY: 61.0},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.TARGET_HUMIDITY: 60.0},
            {ClimateEntityStateAttribute.TARGET_HUMIDITY: 60.9},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.TARGET_TEMP_HIGH: 31.0},
            {ClimateEntityStateAttribute.TARGET_TEMP_HIGH: 31.5},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.TARGET_TEMP_HIGH: 31.0},
            {ClimateEntityStateAttribute.TARGET_TEMP_HIGH: 31.4},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.TARGET_TEMP_LOW: 8.0},
            {ClimateEntityStateAttribute.TARGET_TEMP_LOW: 8.5},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.TARGET_TEMP_LOW: 8.0},
            {ClimateEntityStateAttribute.TARGET_TEMP_LOW: 8.4},
            False,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.TARGET_TEMPERATURE: 22.0},
            {ClimateEntityStateAttribute.TARGET_TEMPERATURE: 22.5},
            True,
        ),
        (
            METRIC,
            {ClimateEntityStateAttribute.TARGET_TEMPERATURE: 22.0},
            {ClimateEntityStateAttribute.TARGET_TEMPERATURE: 22.4},
            False,
        ),
        (
            IMPERIAL,
            {ClimateEntityStateAttribute.TARGET_TEMPERATURE: 70.0},
            {ClimateEntityStateAttribute.TARGET_TEMPERATURE: 71.0},
            True,
        ),
        (
            IMPERIAL,
            {ClimateEntityStateAttribute.TARGET_TEMPERATURE: 70.0},
            {ClimateEntityStateAttribute.TARGET_TEMPERATURE: 70.9},
            False,
        ),
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
