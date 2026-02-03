"""Test lock triggers."""

from typing import Any

import pytest

from homeassistant.components.lock import DOMAIN, LockState
from homeassistant.const import ATTR_LABEL_ID, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components import (
    TriggerStateDescription,
    arm_trigger,
    other_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_locks(hass: HomeAssistant) -> list[str]:
    """Create multiple lock entities associated with different targets."""
    return (await target_entities(hass, DOMAIN))["included"]


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
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


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
    service_calls: list[ServiceCall],
    target_locks: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the lock state trigger fires when any lock state changes to a specific state."""
    other_entity_ids = set(target_locks) - {entity_id}

    # Set all locks, including the tested one, to the initial state
    for eid in target_locks:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other locks also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


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
    service_calls: list[ServiceCall],
    target_locks: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the lock state trigger fires when the first lock changes to a specific state."""
    other_entity_ids = set(target_locks) - {entity_id}

    # Set all locks, including the tested one, to the initial state
    for eid in target_locks:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other locks should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


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
    service_calls: list[ServiceCall],
    target_locks: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the lock state trigger fires when the last lock changes to a specific state."""
    other_entity_ids = set(target_locks) - {entity_id}

    # Set all locks, including the tested one, to the initial state
    for eid in target_locks:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
