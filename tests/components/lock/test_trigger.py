"""Test lock triggers."""

from typing import Any

import pytest

from homeassistant.components.lock import DOMAIN, LockState
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    other_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture
async def target_locks(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple lock entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.mark.parametrize(
    "trigger_key",
    [
        "lock.jammed",
        "lock.locked",
        "lock.opened",
        "lock.unlocked",
    ],
)
async def test_lock_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the lock triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="lock.jammed",
            target_states=[LockState.JAMMED],
            other_states=other_states(LockState.JAMMED),
        ),
        *parametrize_trigger_states(
            trigger="lock.locked",
            target_states=[LockState.LOCKED],
            other_states=other_states(LockState.LOCKED),
        ),
        *parametrize_trigger_states(
            trigger="lock.opened",
            target_states=[LockState.OPEN],
            other_states=other_states(LockState.OPEN),
        ),
        *parametrize_trigger_states(
            trigger="lock.unlocked",
            target_states=[LockState.UNLOCKED],
            other_states=other_states(LockState.UNLOCKED),
        ),
    ],
)
async def test_lock_state_trigger_behavior_any(
    hass: HomeAssistant,
    target_locks: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the lock state trigger fires when any lock state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_locks,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="lock.jammed",
            target_states=[LockState.JAMMED],
            other_states=other_states(LockState.JAMMED),
        ),
        *parametrize_trigger_states(
            trigger="lock.locked",
            target_states=[LockState.LOCKED],
            other_states=other_states(LockState.LOCKED),
        ),
        *parametrize_trigger_states(
            trigger="lock.opened",
            target_states=[LockState.OPEN],
            other_states=other_states(LockState.OPEN),
        ),
        *parametrize_trigger_states(
            trigger="lock.unlocked",
            target_states=[LockState.UNLOCKED],
            other_states=other_states(LockState.UNLOCKED),
        ),
    ],
)
async def test_lock_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_locks: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the lock state trigger fires when the first lock changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_locks,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="lock.jammed",
            target_states=[LockState.JAMMED],
            other_states=other_states(LockState.JAMMED),
        ),
        *parametrize_trigger_states(
            trigger="lock.locked",
            target_states=[LockState.LOCKED],
            other_states=other_states(LockState.LOCKED),
        ),
        *parametrize_trigger_states(
            trigger="lock.opened",
            target_states=[LockState.OPEN],
            other_states=other_states(LockState.OPEN),
        ),
        *parametrize_trigger_states(
            trigger="lock.unlocked",
            target_states=[LockState.UNLOCKED],
            other_states=other_states(LockState.UNLOCKED),
        ),
    ],
)
async def test_lock_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_locks: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the lock state trigger fires when the last lock changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_locks,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
