"""Test water heater conditions."""

from typing import Any

import pytest

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ABOVE,
    CONF_BELOW,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_numerical_condition_unit_conversion,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_numerical_attribute_condition_above_below_all,
    parametrize_numerical_attribute_condition_above_below_any,
    parametrize_target_entities,
    target_entities,
)

_TEMPERATURE_CONDITION_OPTIONS = {"unit": UnitOfTemperature.CELSIUS}

_ALL_STATES = [
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    STATE_ON,
    STATE_PERFORMANCE,
]

_ON_STATES = [s for s in _ALL_STATES if s != STATE_OFF]


@pytest.fixture
async def target_water_heaters(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple water heater entities associated with different targets."""
    return await target_entities(hass, "water_heater")


@pytest.mark.parametrize(
    "condition",
    [
        "water_heater.is_off",
        "water_heater.is_on",
        "water_heater.is_operation_mode",
        "water_heater.is_target_temperature",
    ],
)
async def test_water_heater_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the water heater conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="water_heater.is_off",
            target_states=[STATE_OFF],
            other_states=_ON_STATES,
        ),
        *parametrize_condition_states_any(
            condition="water_heater.is_on",
            target_states=_ON_STATES,
            other_states=[STATE_OFF],
        ),
        *(
            param
            for mode in _ALL_STATES
            for param in parametrize_condition_states_any(
                condition="water_heater.is_operation_mode",
                condition_options={"operation_mode": [mode]},
                target_states=[mode],
                other_states=[s for s in _ALL_STATES if s != mode],
            )
        ),
        *parametrize_condition_states_any(
            condition="water_heater.is_operation_mode",
            condition_options={"operation_mode": ["eco", "electric"]},
            target_states=["eco", "electric"],
            other_states=[s for s in _ALL_STATES if s not in ("eco", "electric")],
        ),
    ],
)
async def test_water_heater_state_condition_behavior_any(
    hass: HomeAssistant,
    target_water_heaters: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the water heater state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_water_heaters,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="water_heater.is_off",
            target_states=[STATE_OFF],
            other_states=_ON_STATES,
        ),
        *parametrize_condition_states_all(
            condition="water_heater.is_on",
            target_states=_ON_STATES,
            other_states=[STATE_OFF],
        ),
        *(
            param
            for mode in _ALL_STATES
            for param in parametrize_condition_states_all(
                condition="water_heater.is_operation_mode",
                condition_options={"operation_mode": [mode]},
                target_states=[mode],
                other_states=[s for s in _ALL_STATES if s != mode],
            )
        ),
        *parametrize_condition_states_all(
            condition="water_heater.is_operation_mode",
            condition_options={"operation_mode": ["eco", "electric"]},
            target_states=["eco", "electric"],
            other_states=[s for s in _ALL_STATES if s not in ("eco", "electric")],
        ),
    ],
)
async def test_water_heater_state_condition_behavior_all(
    hass: HomeAssistant,
    target_water_heaters: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the water heater state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_water_heaters,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_numerical_attribute_condition_above_below_any(
            "water_heater.is_target_temperature",
            "eco",
            ATTR_TEMPERATURE,
            condition_options=_TEMPERATURE_CONDITION_OPTIONS,
        ),
    ],
)
async def test_water_heater_numerical_condition_behavior_any(
    hass: HomeAssistant,
    target_water_heaters: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the water heater numerical condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_water_heaters,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_numerical_attribute_condition_above_below_all(
            "water_heater.is_target_temperature",
            "eco",
            ATTR_TEMPERATURE,
            condition_options=_TEMPERATURE_CONDITION_OPTIONS,
        ),
    ],
)
async def test_water_heater_numerical_condition_behavior_all(
    hass: HomeAssistant,
    target_water_heaters: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the water heater numerical condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_water_heaters,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_water_heater_numerical_condition_unit_conversion(
    hass: HomeAssistant,
) -> None:
    """Test that the water heater numerical condition converts units correctly."""
    _unit_celsius = {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    _unit_fahrenheit = {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT}
    _unit_invalid = {ATTR_UNIT_OF_MEASUREMENT: "not_a_valid_unit"}

    await assert_numerical_condition_unit_conversion(
        hass,
        condition="water_heater.is_target_temperature",
        entity_id="water_heater.test",
        pass_states=[{"state": "eco", "attributes": {ATTR_TEMPERATURE: 55}}],
        fail_states=[
            {
                "state": "eco",
                "attributes": {ATTR_TEMPERATURE: 40},
            }
        ],
        numerical_condition_options=[
            {CONF_ABOVE: 120, CONF_BELOW: 140, "unit": UnitOfTemperature.FAHRENHEIT},
            {CONF_ABOVE: 49, CONF_BELOW: 60, "unit": UnitOfTemperature.CELSIUS},
        ],
        limit_entity_condition_options={
            CONF_ABOVE: "sensor.above",
            CONF_BELOW: "sensor.below",
        },
        limit_entities=("sensor.above", "sensor.below"),
        limit_entity_states=[
            (
                {"state": "120", "attributes": _unit_fahrenheit},  # ≈48.9°C
                {"state": "140", "attributes": _unit_fahrenheit},  # ≈60.0°C
            ),
            (
                {"state": "49", "attributes": _unit_celsius},
                {"state": "60", "attributes": _unit_celsius},
            ),
        ],
        invalid_limit_entity_states=[
            (
                {"state": "120", "attributes": _unit_invalid},
                {"state": "140", "attributes": _unit_invalid},
            ),
            (
                {"state": "49", "attributes": _unit_invalid},
                {"state": "60", "attributes": _unit_invalid},
            ),
        ],
    )
