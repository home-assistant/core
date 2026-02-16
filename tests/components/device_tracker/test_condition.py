"""Test device tracker conditions."""

from typing import Any

import pytest

from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant

from tests.components import (
    ConditionStateDescription,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_device_trackers(hass: HomeAssistant) -> list[str]:
    """Create multiple device tracker entities associated with different targets."""
    return (await target_entities(hass, "device_tracker"))["included"]


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
    target_device_trackers: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the device tracker state condition with the 'any' behavior."""
    other_entity_ids = set(target_device_trackers) - {entity_id}

    # Set all device trackers, including the tested one, to the initial state
    for eid in target_device_trackers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
    )

    for state in states:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]

        # Check if changing other device trackers also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


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
    target_device_trackers: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the device tracker state condition with the 'all' behavior."""
    other_entity_ids = set(target_device_trackers) - {entity_id}

    # Set all device trackers, including the tested one, to the initial state
    for eid in target_device_trackers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="all",
    )

    for state in states:
        included_state = state["included"]

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true_first_entity"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()

        assert condition(hass) == state["condition_true"]
