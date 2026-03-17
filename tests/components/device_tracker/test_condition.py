"""Test device tracker conditions."""

from typing import Any

import pytest

from homeassistant.const import STATE_HOME, STATE_NOT_HOME
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
async def target_device_trackers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple device tracker entities associated with different targets."""
    return await target_entities(hass, "device_tracker")


@pytest.mark.parametrize(
    "condition",
    [
        "device_tracker.is_home",
        "device_tracker.is_not_home",
    ],
)
async def test_device_tracker_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the device tracker conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="device_tracker.is_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME],
        ),
        *parametrize_condition_states_any(
            condition="device_tracker.is_not_home",
            target_states=[STATE_NOT_HOME],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_device_tracker_state_condition_behavior_any(
    hass: HomeAssistant,
    target_device_trackers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the device tracker state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_device_trackers,
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
    parametrize_target_entities("device_tracker"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="device_tracker.is_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME],
        ),
        *parametrize_condition_states_all(
            condition="device_tracker.is_not_home",
            target_states=[STATE_NOT_HOME],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_device_tracker_state_condition_behavior_all(
    hass: HomeAssistant,
    target_device_trackers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the device tracker state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_device_trackers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
