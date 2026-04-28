"""Test schedule conditions."""

from typing import Any

import pytest

from homeassistant.components.schedule.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
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
async def target_schedules(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple schedule entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.mark.parametrize(
    "condition",
    [
        "schedule.is_off",
        "schedule.is_on",
    ],
)
async def test_schedule_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the schedule conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="schedule.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states_any(
            condition="schedule.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_schedule_state_condition_behavior_any(
    hass: HomeAssistant,
    target_schedules: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the schedule state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_schedules,
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
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="schedule.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states_all(
            condition="schedule.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_schedule_state_condition_behavior_all(
    hass: HomeAssistant,
    target_schedules: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the schedule state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_schedules,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
