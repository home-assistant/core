"""Tests the lock platform of the Loqed integration."""

import aiohttp
from loqedAPI import loqed
import pytest

from homeassistant.components.lock import LockState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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


async def test_lock_unknown_bolt_state_is_unknown(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test an unknown bolt state from the bridge is shown as unknown, not unlocked."""
    lock.bolt_state = "unknown"
    integration.runtime_data.async_update_listeners()

    state = hass.states.get("lock.home")
    assert state
    assert state.state == STATE_UNKNOWN


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


@pytest.mark.parametrize(
    ("service", "mock_method"),
    [
        (SERVICE_LOCK, "lock"),
        (SERVICE_UNLOCK, "unlock"),
        (SERVICE_OPEN, "open"),
    ],
)
@pytest.mark.parametrize(
    "exception",
    [TimeoutError, aiohttp.ClientError],
)
async def test_lock_action_raises_on_communication_failure(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    lock: loqed.Lock,
    service: str,
    mock_method: str,
    exception: type[Exception],
) -> None:
    """Test lock actions raise HomeAssistantError on bridge communication failure."""
    entity_id = "lock.home"
    getattr(lock, mock_method).side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "lock", service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
