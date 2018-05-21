"""Test different accessory types: Locks."""
import pytest

from homeassistant.components.homekit.type_locks import Lock
from homeassistant.components.lock import DOMAIN
from homeassistant.const import (
    ATTR_CODE, ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNKNOWN, STATE_UNLOCKED)

from tests.common import async_mock_service


async def test_lock_unlock(hass):
    """Test if accessory and HA are updated accordingly."""
    code = '1234'
    config = {ATTR_CODE: code}
    entity_id = 'lock.kitchen_door'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Lock(hass, 'Lock', entity_id, 2, config)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 6  # DoorLock

    assert acc.char_current_state.value == 3
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, STATE_LOCKED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 1
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, STATE_UNLOCKED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 3
    assert acc.char_target_state.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 3
    assert acc.char_target_state.value == 0

    # Set from HomeKit
    call_lock = async_mock_service(hass, DOMAIN, 'lock')
    call_unlock = async_mock_service(hass, DOMAIN, 'unlock')

    await hass.async_add_job(acc.char_target_state.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_lock
    assert call_lock[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_lock[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 1

    await hass.async_add_job(acc.char_target_state.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_unlock
    assert call_unlock[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_unlock[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 0


@pytest.mark.parametrize('config', [{}, {ATTR_CODE: None}])
async def test_no_code(hass, config):
    """Test accessory if lock doesn't require a code."""
    entity_id = 'lock.kitchen_door'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Lock(hass, 'Lock', entity_id, 2, config)

    # Set from HomeKit
    call_lock = async_mock_service(hass, DOMAIN, 'lock')

    await hass.async_add_job(acc.char_target_state.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_lock
    assert call_lock[0].data[ATTR_ENTITY_ID] == entity_id
    assert ATTR_CODE not in call_lock[0].data
    assert acc.char_target_state.value == 1
