"""Test to-do list conditions."""

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
async def target_todos(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple to-do list entities associated with different targets."""
    return await target_entities(hass, "todo", domain_excluded="sensor")


@pytest.mark.parametrize(
    "condition",
    [
        "todo.all_completed",
        "todo.incomplete",
    ],
)
async def test_todo_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the to-do list conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("todo"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="todo.all_completed",
            target_states=["0"],
            other_states=["1", "5"],
            excluded_entities_from_other_domain=True,
        ),
    ],
)
async def test_todo_state_condition_behavior_any(
    hass: HomeAssistant,
    target_todos: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the to-do list state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_todos,
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
    parametrize_target_entities("todo"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="todo.all_completed",
            target_states=["0"],
            other_states=["1", "5"],
            excluded_entities_from_other_domain=True,
        ),
    ],
)
async def test_todo_state_condition_behavior_all(
    hass: HomeAssistant,
    target_todos: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the to-do list state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_todos,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


def parametrize_incomplete_condition_states_any(
    condition: str,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize above/below threshold test cases for incomplete conditions."""
    return [
        *parametrize_condition_states_any(
            condition=condition,
            condition_options={"threshold": {"type": "above", "value": {"number": 3}}},
            target_states=["5", "10"],
            other_states=["0", "1", "3"],
        ),
        *parametrize_condition_states_any(
            condition=condition,
            condition_options={"threshold": {"type": "below", "value": {"number": 5}}},
            target_states=["0", "3"],
            other_states=["5", "10"],
        ),
        *parametrize_condition_states_any(
            condition=condition,
            condition_options={
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 2},
                    "value_max": {"number": 8},
                }
            },
            target_states=["3", "5"],
            other_states=["0", "1", "2", "8", "10"],
        ),
    ]


def parametrize_incomplete_condition_states_all(
    condition: str,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize above/below threshold test cases for incomplete conditions with 'all' behavior."""
    return [
        *parametrize_condition_states_all(
            condition=condition,
            condition_options={"threshold": {"type": "above", "value": {"number": 3}}},
            target_states=["5", "10"],
            other_states=["0", "1", "3"],
        ),
        *parametrize_condition_states_all(
            condition=condition,
            condition_options={"threshold": {"type": "below", "value": {"number": 5}}},
            target_states=["0", "3"],
            other_states=["5", "10"],
        ),
        *parametrize_condition_states_all(
            condition=condition,
            condition_options={
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 2},
                    "value_max": {"number": 8},
                }
            },
            target_states=["3", "5"],
            other_states=["0", "1", "2", "8", "10"],
        ),
    ]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("todo"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_incomplete_condition_states_any("todo.incomplete"),
    ],
)
async def test_todo_incomplete_condition_behavior_any(
    hass: HomeAssistant,
    target_todos: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the to-do list incomplete condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_todos,
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
    parametrize_target_entities("todo"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_incomplete_condition_states_all("todo.incomplete"),
    ],
)
async def test_todo_incomplete_condition_behavior_all(
    hass: HomeAssistant,
    target_todos: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the to-do list incomplete condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_todos,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
