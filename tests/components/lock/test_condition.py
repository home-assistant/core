"""Test lock conditions."""

from typing import Any

import pytest

from homeassistant.components.lock.const import LockState
from homeassistant.core import HomeAssistant

from tests.components import (
    ConditionStateDescription,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_locks(hass: HomeAssistant) -> list[str]:
    """Create multiple lock entities associated with different targets."""
    return (await target_entities(hass, "lock"))["included"]


@pytest.mark.parametrize(
    "condition",
    [
        "lock.is_jammed",
        "lock.is_locked",
        "lock.is_open",
        "lock.is_unlocked",
    ],
)
async def test_lock_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the lock conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("lock"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="lock.is_jammed",
            target_states=[LockState.JAMMED],
            other_states=other_states(LockState.JAMMED),
        ),
        *parametrize_condition_states_any(
            condition="lock.is_locked",
            target_states=[LockState.LOCKED],
            other_states=other_states(LockState.LOCKED),
        ),
        *parametrize_condition_states_any(
            condition="lock.is_open",
            target_states=[LockState.OPEN],
            other_states=other_states(LockState.OPEN),
        ),
        *parametrize_condition_states_any(
            condition="lock.is_unlocked",
            target_states=[LockState.UNLOCKED],
            other_states=other_states(LockState.UNLOCKED),
        ),
    ],
)
async def test_lock_state_condition_behavior_any(
    hass: HomeAssistant,
    target_locks: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the lock state condition with the 'any' behavior."""
    other_entity_ids = set(target_locks) - {entity_id}

    # Set all locks, including the tested lock, to the initial state
    for eid in target_locks:
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

        # Check if changing other locks also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("lock"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="lock.is_jammed",
            target_states=[LockState.JAMMED],
            other_states=other_states(LockState.JAMMED),
        ),
        *parametrize_condition_states_all(
            condition="lock.is_locked",
            target_states=[LockState.LOCKED],
            other_states=other_states(LockState.LOCKED),
        ),
        *parametrize_condition_states_all(
            condition="lock.is_open",
            target_states=[LockState.OPEN],
            other_states=other_states(LockState.OPEN),
        ),
        *parametrize_condition_states_all(
            condition="lock.is_unlocked",
            target_states=[LockState.UNLOCKED],
            other_states=other_states(LockState.UNLOCKED),
        ),
    ],
)
async def test_lock_state_condition_behavior_all(
    hass: HomeAssistant,
    target_locks: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the lock state condition with the 'all' behavior."""
    other_entity_ids = set(target_locks) - {entity_id}

    # Set all locks, including the tested lock, to the initial state
    for eid in target_locks:
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
