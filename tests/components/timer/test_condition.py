"""Test timer conditions."""

from typing import Any

import pytest

from homeassistant.components.timer import STATUS_ACTIVE, STATUS_IDLE, STATUS_PAUSED
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
async def target_timers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple timer entities associated with different targets."""
    return await target_entities(hass, "timer")


@pytest.mark.parametrize(
    "condition",
    [
        "timer.is_active",
        "timer.is_paused",
        "timer.is_idle",
    ],
)
async def test_timer_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the timer conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("timer"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="timer.is_active",
            target_states=[STATUS_ACTIVE],
            other_states=[STATUS_IDLE, STATUS_PAUSED],
        ),
        *parametrize_condition_states_any(
            condition="timer.is_paused",
            target_states=[STATUS_PAUSED],
            other_states=[STATUS_IDLE, STATUS_ACTIVE],
        ),
        *parametrize_condition_states_any(
            condition="timer.is_idle",
            target_states=[STATUS_IDLE],
            other_states=[STATUS_ACTIVE, STATUS_PAUSED],
        ),
    ],
)
async def test_timer_condition_behavior_any(
    hass: HomeAssistant,
    target_timers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test timer condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_timers,
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
    parametrize_target_entities("timer"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="timer.is_active",
            target_states=[STATUS_ACTIVE],
            other_states=[STATUS_IDLE, STATUS_PAUSED],
        ),
        *parametrize_condition_states_all(
            condition="timer.is_paused",
            target_states=[STATUS_PAUSED],
            other_states=[STATUS_IDLE, STATUS_ACTIVE],
        ),
        *parametrize_condition_states_all(
            condition="timer.is_idle",
            target_states=[STATUS_IDLE],
            other_states=[STATUS_ACTIVE, STATUS_PAUSED],
        ),
    ],
)
async def test_timer_condition_behavior_all(
    hass: HomeAssistant,
    target_timers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test timer condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_timers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
