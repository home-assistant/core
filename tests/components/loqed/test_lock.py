"""Tests the lock platform of the Loqed integration."""

from unittest.mock import patch

from loqedAPI import loqed

from homeassistant.components.lock import LockState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_lock_entity(
    hass: HomeAssistant,
    integration: MockConfigEntry,
) -> None:
    """Test the lock entity."""
    entity_id = "lock.home"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == LockState.UNLOCKED


async def test_lock_responds_to_bolt_state_updates(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Tests the lock responding to updates."""
    coordinator = integration.runtime_data
    lock.bolt_state = "night_lock"
    coordinator.async_update_listeners()

    entity_id = "lock.home"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == LockState.LOCKED


async def test_lock_applies_polled_bolt_state(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test a coordinator refresh applies the polled bolt state to the lock."""
    lock.updateState.side_effect = lambda state: setattr(lock, "bolt_state", state)
    coordinator = integration.runtime_data
    with patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock_details",
        return_value={"bolt_state": "night_lock", "lock_online": 1},
    ):
        await coordinator.async_refresh()

    lock.updateState.assert_awaited_with("night_lock")
    state = hass.states.get("lock.home")
    assert state
    assert state.state == LockState.LOCKED


async def test_lock_transition_to_unlocked(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Tests the lock transitions to unlocked state."""

    entity_id = "lock.home"

    await hass.services.async_call(
        "lock", SERVICE_UNLOCK, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    lock.unlock.assert_called()


async def test_lock_transition_to_locked(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Tests the lock transitions to locked state."""

    entity_id = "lock.home"

    await hass.services.async_call(
        "lock", SERVICE_LOCK, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    lock.lock.assert_called()


async def test_lock_transition_to_open(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Tests the lock transitions to open state."""

    entity_id = "lock.home"

    await hass.services.async_call(
        "lock", SERVICE_OPEN, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    lock.open.assert_called()
