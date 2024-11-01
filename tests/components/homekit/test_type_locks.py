"""Test different accessory types: Locks."""

import pytest

from homeassistant.components.homekit.const import ATTR_VALUE
from homeassistant.components.homekit.type_locks import Lock
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant

from tests.common import async_mock_service


async def test_lock_unlock(hass: HomeAssistant, hk_driver, events: list[Event]) -> None:
    """Test if accessory and HA are updated accordingly."""
    code = "1234"
    config = {ATTR_CODE: code}
    entity_id = "lock.kitchen_door"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Lock(hass, hk_driver, "Lock", entity_id, 2, config)
    acc.run()

    assert acc.aid == 2
    assert acc.category == 6  # DoorLock

    assert acc.char_current_state.value == 3
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, LockState.LOCKED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 1
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, LockState.LOCKING)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, LockState.UNLOCKED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, LockState.UNLOCKING)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 1
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, LockState.JAMMED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 2
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 2
    assert acc.char_target_state.value == 0

    # Unavailable should keep last state
    # but set the accessory to not available
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 2
    assert acc.char_target_state.value == 0
    assert acc.available is False

    hass.states.async_set(entity_id, LockState.UNLOCKED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0
    assert acc.available is True

    # Unavailable should keep last state
    # but set the accessory to not available
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0
    assert acc.available is False

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0

    # Set from HomeKit
    call_lock = async_mock_service(hass, LOCK_DOMAIN, "lock")
    call_unlock = async_mock_service(hass, LOCK_DOMAIN, "unlock")

    acc.char_target_state.client_update_value(1)
    await hass.async_block_till_done()
    assert call_lock
    assert call_lock[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_lock[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 1
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_state.client_update_value(0)
    await hass.async_block_till_done()
    assert call_unlock
    assert call_unlock[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_unlock[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 0
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


@pytest.mark.parametrize("config", [{}, {ATTR_CODE: None}])
async def test_no_code(
    hass: HomeAssistant, hk_driver, config, events: list[Event]
) -> None:
    """Test accessory if lock doesn't require a code."""
    entity_id = "lock.kitchen_door"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Lock(hass, hk_driver, "Lock", entity_id, 2, config)

    # Set from HomeKit
    call_lock = async_mock_service(hass, LOCK_DOMAIN, "lock")

    acc.char_target_state.client_update_value(1)
    await hass.async_block_till_done()
    assert call_lock
    assert call_lock[0].data[ATTR_ENTITY_ID] == entity_id
    assert ATTR_CODE not in call_lock[0].data
    assert acc.char_target_state.value == 1
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None
