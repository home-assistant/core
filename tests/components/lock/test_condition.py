"""Test lock conditions."""

from typing import Any

import pytest

from homeassistant.components.lock.const import LockState
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_locks(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple lock entities associated with different targets."""
    return await target_entities(hass, "lock")


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
    target_locks: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the lock state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_locks,
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
    target_locks: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the lock state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_locks,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
