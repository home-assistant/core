"""Test calendar conditions."""

from typing import Any

import pytest

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
async def target_calendars(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple calendar entities associated with different targets."""
    return await target_entities(hass, "calendar")


@pytest.mark.parametrize(
    "condition",
    [
        "calendar.is_event_active",
    ],
)
async def test_calendar_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the calendar conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("calendar"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="calendar.is_event_active",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_calendar_condition_behavior_any(
    hass: HomeAssistant,
    target_calendars: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test calendar condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_calendars,
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
    parametrize_target_entities("calendar"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="calendar.is_event_active",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_calendar_condition_behavior_all(
    hass: HomeAssistant,
    target_calendars: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test calendar condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_calendars,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
