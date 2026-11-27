"""Test the Water Heater significant change platform."""

import pytest

from homeassistant.components.water_heater import WaterHeaterStateAttribute
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
        (
            METRIC,
            {WaterHeaterStateAttribute.AWAY_MODE: "old_value"},
            {WaterHeaterStateAttribute.AWAY_MODE: "old_value"},
            False,
        ),
        (
            METRIC,
            {WaterHeaterStateAttribute.AWAY_MODE: "old_value"},
            {WaterHeaterStateAttribute.AWAY_MODE: "new_value"},
            True,
        ),
        (
            METRIC,
            {WaterHeaterStateAttribute.OPERATION_MODE: "old_value"},
            {WaterHeaterStateAttribute.OPERATION_MODE: "new_value"},
            True,
        ),
        # multiple attributes
        (
            METRIC,
            {
                WaterHeaterStateAttribute.AWAY_MODE: "old_value",
                WaterHeaterStateAttribute.OPERATION_MODE: "old_value",
            },
            {
                WaterHeaterStateAttribute.AWAY_MODE: "new_value",
                WaterHeaterStateAttribute.OPERATION_MODE: "old_value",
            },
            True,
        ),
        # float attributes
        (
            METRIC,
            {WaterHeaterStateAttribute.CURRENT_TEMPERATURE: 50.0},
            {WaterHeaterStateAttribute.CURRENT_TEMPERATURE: 50.5},
            True,
        ),
        (
            METRIC,
            {WaterHeaterStateAttribute.CURRENT_TEMPERATURE: 50.0},
            {WaterHeaterStateAttribute.CURRENT_TEMPERATURE: 50.4},
            False,
        ),
        (
            METRIC,
            {WaterHeaterStateAttribute.CURRENT_TEMPERATURE: "invalid"},
            {WaterHeaterStateAttribute.CURRENT_TEMPERATURE: 10.0},
            True,
        ),
        (
            METRIC,
            {WaterHeaterStateAttribute.CURRENT_TEMPERATURE: 10.0},
            {WaterHeaterStateAttribute.CURRENT_TEMPERATURE: "invalid"},
            False,
        ),
        (
            IMPERIAL,
            {WaterHeaterStateAttribute.TARGET_TEMPERATURE: 160.0},
            {WaterHeaterStateAttribute.TARGET_TEMPERATURE: 161},
            True,
        ),
        (
            IMPERIAL,
            {WaterHeaterStateAttribute.TARGET_TEMPERATURE: 160.0},
            {WaterHeaterStateAttribute.TARGET_TEMPERATURE: 160.9},
            False,
        ),
        (
            METRIC,
            {WaterHeaterStateAttribute.TARGET_TEMP_HIGH: 80.0},
            {WaterHeaterStateAttribute.TARGET_TEMP_HIGH: 80.5},
            True,
        ),
        (
            METRIC,
            {WaterHeaterStateAttribute.TARGET_TEMP_HIGH: 80.0},
            {WaterHeaterStateAttribute.TARGET_TEMP_HIGH: 80.4},
            False,
        ),
        (
            METRIC,
            {WaterHeaterStateAttribute.TARGET_TEMP_LOW: 30.0},
            {WaterHeaterStateAttribute.TARGET_TEMP_LOW: 30.5},
            True,
        ),
        (
            METRIC,
            {WaterHeaterStateAttribute.TARGET_TEMP_LOW: 30.0},
            {WaterHeaterStateAttribute.TARGET_TEMP_LOW: 30.4},
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
    """Detect Water Heater significant attribute changes."""
    hass.config.units = unit_system
    assert (
        async_check_significant_change(hass, "state", old_attrs, "state", new_attrs)
        == expected_result
    )
