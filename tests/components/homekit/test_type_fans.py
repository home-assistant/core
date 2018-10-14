"""Test different accessory types: Fans."""
from collections import namedtuple

import pytest

from homeassistant.components.fan import (
    ATTR_DIRECTION, ATTR_OSCILLATING, DIRECTION_FORWARD, DIRECTION_REVERSE,
    DOMAIN, SUPPORT_DIRECTION, SUPPORT_OSCILLATE)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, STATE_ON, STATE_OFF,
    STATE_UNKNOWN)

from tests.common import async_mock_service
from tests.components.homekit.common import patch_debounce


@pytest.fixture(scope='module')
def cls():
    """Patch debounce decorator during import of type_fans."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__('homeassistant.components.homekit.type_fans',
                         fromlist=['Fan'])
    patcher_tuple = namedtuple('Cls', ['fan'])
    yield patcher_tuple(fan=_import.Fan)
    patcher.stop()


async def test_fan_basic(hass, hk_driver, cls):
    """Test fan with char state."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, 'Fan', entity_id, 2, None)

    assert acc.aid == 2
    assert acc.category == 3  # Fan
    assert acc.char_active.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_active.value == 1

    hass.states.async_set(entity_id, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, 'turn_on')
    call_turn_off = async_mock_service(hass, DOMAIN, 'turn_off')

    await hass.async_add_job(acc.char_active.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    await hass.async_add_job(acc.char_active.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id


async def test_fan_direction(hass, hk_driver, cls):
    """Test fan with direction."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_DIRECTION,
        ATTR_DIRECTION: DIRECTION_FORWARD})
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, 'Fan', entity_id, 2, None)

    assert acc.char_direction.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_direction.value == 0

    hass.states.async_set(entity_id, STATE_ON,
                          {ATTR_DIRECTION: DIRECTION_REVERSE})
    await hass.async_block_till_done()
    assert acc.char_direction.value == 1

    # Set from HomeKit
    call_set_direction = async_mock_service(hass, DOMAIN, 'set_direction')

    await hass.async_add_job(acc.char_direction.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_set_direction[0]
    assert call_set_direction[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[0].data[ATTR_DIRECTION] == DIRECTION_FORWARD

    await hass.async_add_job(acc.char_direction.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_set_direction[1]
    assert call_set_direction[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[1].data[ATTR_DIRECTION] == DIRECTION_REVERSE


async def test_fan_oscillate(hass, hk_driver, cls):
    """Test fan with oscillate."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_OSCILLATE, ATTR_OSCILLATING: False})
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, 'Fan', entity_id, 2, None)

    assert acc.char_swing.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_swing.value == 0

    hass.states.async_set(entity_id, STATE_ON, {ATTR_OSCILLATING: True})
    await hass.async_block_till_done()
    assert acc.char_swing.value == 1

    # Set from HomeKit
    call_oscillate = async_mock_service(hass, DOMAIN, 'oscillate')

    await hass.async_add_job(acc.char_swing.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_oscillate[0]
    assert call_oscillate[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[0].data[ATTR_OSCILLATING] is False

    await hass.async_add_job(acc.char_swing.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_oscillate[1]
    assert call_oscillate[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[1].data[ATTR_OSCILLATING] is True
