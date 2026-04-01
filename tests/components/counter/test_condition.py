"""Test counter conditions."""

from typing import Any

import pytest

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
async def target_counters(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple counter entities associated with different targets."""
    return await target_entities(hass, "counter")


async def test_counter_condition_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the counter condition is gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, "counter.is_value")


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("counter"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="counter.is_value",
            condition_options={
                "threshold": {"type": "above", "value": {"number": 20}},
            },
            target_states=["21", "50", "100"],
            other_states=["0", "10", "20"],
        ),
        *parametrize_condition_states_any(
            condition="counter.is_value",
            condition_options={
                "threshold": {"type": "below", "value": {"number": 20}},
            },
            target_states=["0", "10", "19"],
            other_states=["20", "50", "100"],
        ),
        *parametrize_condition_states_any(
            condition="counter.is_value",
            condition_options={
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"number": 30},
                },
            },
            target_states=["11", "20", "29"],
            other_states=["0", "10", "30", "100"],
        ),
        *parametrize_condition_states_any(
            condition="counter.is_value",
            condition_options={
                "threshold": {
                    "type": "outside",
                    "value_min": {"number": 10},
                    "value_max": {"number": 30},
                },
            },
            target_states=["0", "10", "30", "100"],
            other_states=["11", "20", "29"],
        ),
    ],
)
async def test_counter_is_value_condition_behavior_any(
    hass: HomeAssistant,
    target_counters: dict[str, list[str]],
    condition_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the counter is_value condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_counters,
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
    parametrize_target_entities("counter"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="counter.is_value",
            condition_options={
                "threshold": {"type": "above", "value": {"number": 20}},
            },
            target_states=["21", "50", "100"],
            other_states=["0", "10", "20"],
        ),
        *parametrize_condition_states_all(
            condition="counter.is_value",
            condition_options={
                "threshold": {"type": "below", "value": {"number": 20}},
            },
            target_states=["0", "10", "19"],
            other_states=["20", "50", "100"],
        ),
        *parametrize_condition_states_all(
            condition="counter.is_value",
            condition_options={
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"number": 30},
                },
            },
            target_states=["11", "20", "29"],
            other_states=["0", "10", "30", "100"],
        ),
        *parametrize_condition_states_all(
            condition="counter.is_value",
            condition_options={
                "threshold": {
                    "type": "outside",
                    "value_min": {"number": 10},
                    "value_max": {"number": 30},
                },
            },
            target_states=["0", "10", "30", "100"],
            other_states=["11", "20", "29"],
        ),
    ],
)
async def test_counter_is_value_condition_behavior_all(
    hass: HomeAssistant,
    target_counters: dict[str, list[str]],
    condition_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the counter is_value condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_counters,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
