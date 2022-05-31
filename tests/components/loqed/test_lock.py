"""Tests the lock platform of the Loqed integration."""
import json

from loqedAPI import loqed

from homeassistant.components.loqed import LoqedDataCoordinator
from homeassistant.components.loqed.const import CONF_COORDINATOR, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


async def test_lock_entity(
    hass: HomeAssistant,
    integration: MockConfigEntry,
) -> None:
    """Test the lock entity."""
    entity_id = "lock.loqed_smart_lock"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNLOCKED


async def test_lock_responds_to_updates(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Test the lock responding to updates."""
    coordinator: LoqedDataCoordinator = hass.data[DOMAIN][integration.entry_id][
        CONF_COORDINATOR
    ]
    coordinator.async_set_updated_data(
        {
            "go_to_state": "DAY_LOCK",
        }
    )

    entity_id = "lock.loqed_smart_lock"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNLOCKING


async def test_lock_responds_to_status_updates(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Tests the lock responding to updates."""
    message = json.loads(load_fixture("loqed/lock_going_to_daylock.json"))

    coordinator: LoqedDataCoordinator = hass.data[DOMAIN][integration.entry_id][
        CONF_COORDINATOR
    ]
    coordinator.async_set_updated_data(message)

    entity_id = "lock.loqed_smart_lock"
    print(hass.state)
    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNLOCKING


async def test_lock_responds_to_webhook_calls(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Tests the lock responding to updates."""
    message = json.loads(load_fixture("loqed/nightlock_reached.json"))

    coordinator: LoqedDataCoordinator = hass.data[DOMAIN][integration.entry_id][
        CONF_COORDINATOR
    ]
    coordinator.async_set_updated_data(message)

    entity_id = "lock.loqed_smart_lock"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_LOCKED


async def test_lock_responds_to_bolt_state_updates(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Tests the lock responding to updates."""
    coordinator: LoqedDataCoordinator = hass.data[DOMAIN][integration.entry_id][
        CONF_COORDINATOR
    ]
    coordinator.async_set_updated_data(
        {
            "bolt_state": "night_lock",
        }
    )

    entity_id = "lock.loqed_smart_lock"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_LOCKED


async def test_lock_transition_to_unlocked(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Tests the lock transitions to unlocked state."""

    entity_id = "lock.loqed_smart_lock"

    await hass.services.async_call(
        "lock", SERVICE_UNLOCK, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    lock.unlock.assert_called()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNLOCKING


async def test_lock_transition_to_locked(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Tests the lock transitions to locked state."""

    entity_id = "lock.loqed_smart_lock"

    await hass.services.async_call(
        "lock", SERVICE_LOCK, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    lock.lock.assert_called()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_LOCKING


async def test_lock_transition_to_open(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Tests the lock transitions to open state."""

    entity_id = "lock.loqed_smart_lock"

    await hass.services.async_call(
        "lock", SERVICE_OPEN, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    lock.open.assert_called()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNLOCKING
