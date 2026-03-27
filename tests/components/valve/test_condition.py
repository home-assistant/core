"""Test valve conditions."""

from typing import Any

import pytest

from homeassistant.components.valve import ATTR_IS_CLOSED
from homeassistant.components.valve.const import ValveState
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_valves(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple valve entities associated with different targets."""
    return await target_entities(hass, "valve")


@pytest.mark.parametrize(
    "condition",
    [
        "valve.is_open",
        "valve.is_closed",
    ],
)
async def test_valve_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the valve conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("valve"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="valve.is_open",
            target_states=[
                (ValveState.OPEN, {ATTR_IS_CLOSED: False}),
                (ValveState.OPENING, {ATTR_IS_CLOSED: False}),
                (ValveState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (ValveState.CLOSED, {ATTR_IS_CLOSED: True}),
                (ValveState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
        ),
        *parametrize_condition_states_any(
            condition="valve.is_closed",
            target_states=[
                (ValveState.CLOSED, {ATTR_IS_CLOSED: True}),
                (ValveState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (ValveState.OPEN, {ATTR_IS_CLOSED: False}),
                (ValveState.OPENING, {ATTR_IS_CLOSED: False}),
                (ValveState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
        ),
    ],
)
async def test_valve_condition_behavior_any(
    hass: HomeAssistant,
    target_valves: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test valve condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_valves,
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
    parametrize_target_entities("valve"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="valve.is_open",
            target_states=[
                (ValveState.OPEN, {ATTR_IS_CLOSED: False}),
                (ValveState.OPENING, {ATTR_IS_CLOSED: False}),
                (ValveState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (ValveState.CLOSED, {ATTR_IS_CLOSED: True}),
                (ValveState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
        ),
        *parametrize_condition_states_all(
            condition="valve.is_closed",
            target_states=[
                (ValveState.CLOSED, {ATTR_IS_CLOSED: True}),
                (ValveState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (ValveState.OPEN, {ATTR_IS_CLOSED: False}),
                (ValveState.OPENING, {ATTR_IS_CLOSED: False}),
                (ValveState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
        ),
    ],
)
async def test_valve_condition_behavior_all(
    hass: HomeAssistant,
    target_valves: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test valve condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_valves,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
