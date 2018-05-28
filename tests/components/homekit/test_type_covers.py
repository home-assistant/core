"""Test different accessory types: Covers."""
from collections import namedtuple

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION, ATTR_POSITION, DOMAIN, SUPPORT_STOP)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES,
    STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE, STATE_UNKNOWN)

from tests.common import async_mock_service
from tests.components.homekit.common import patch_debounce


@pytest.fixture(scope='module')
def cls():
    """Patch debounce decorator during import of type_covers."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__('homeassistant.components.homekit.type_covers',
                         fromlist=['GarageDoorOpener', 'WindowCovering,',
                                   'WindowCoveringBasic'])
    patcher_tuple = namedtuple('Cls', ['window', 'window_basic', 'garage'])
    yield patcher_tuple(window=_import.WindowCovering,
                        window_basic=_import.WindowCoveringBasic,
                        garage=_import.GarageDoorOpener)
    patcher.stop()


async def test_garage_door_open_close(hass, cls):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'cover.garage_door'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = cls.garage(hass, 'Garage Door', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 4  # GarageDoorOpener

    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, STATE_CLOSED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 1
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, STATE_OPEN)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0

    # Set from HomeKit
    call_close_cover = async_mock_service(hass, DOMAIN, 'close_cover')
    call_open_cover = async_mock_service(hass, DOMAIN, 'open_cover')

    await hass.async_add_job(acc.char_target_state.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_close_cover
    assert call_close_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_state.value == 2
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, STATE_CLOSED)
    await hass.async_block_till_done()

    await hass.async_add_job(acc.char_target_state.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_open_cover
    assert call_open_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_state.value == 3
    assert acc.char_target_state.value == 0


async def test_window_set_cover_position(hass, cls):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'cover.window'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = cls.window(hass, 'Cover', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 14  # WindowCovering

    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN,
                          {ATTR_CURRENT_POSITION: None})
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0

    hass.states.async_set(entity_id, STATE_OPEN,
                          {ATTR_CURRENT_POSITION: 50})
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 50

    # Set from HomeKit
    call_set_cover_position = async_mock_service(hass, DOMAIN,
                                                 'set_cover_position')

    await hass.async_add_job(acc.char_target_position.client_update_value, 25)
    await hass.async_block_till_done()
    assert call_set_cover_position[0]
    assert call_set_cover_position[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_cover_position[0].data[ATTR_POSITION] == 25
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 25

    await hass.async_add_job(acc.char_target_position.client_update_value, 75)
    await hass.async_block_till_done()
    assert call_set_cover_position[1]
    assert call_set_cover_position[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_cover_position[1].data[ATTR_POSITION] == 75
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 75


async def test_window_open_close(hass, cls):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'cover.window'

    hass.states.async_set(entity_id, STATE_UNKNOWN,
                          {ATTR_SUPPORTED_FEATURES: 0})
    acc = cls.window_basic(hass, 'Cover', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 14  # WindowCovering

    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2

    hass.states.async_set(entity_id, STATE_OPEN)
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 100
    assert acc.char_target_position.value == 100
    assert acc.char_position_state.value == 2

    hass.states.async_set(entity_id, STATE_CLOSED)
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2

    # Set from HomeKit
    call_close_cover = async_mock_service(hass, DOMAIN, 'close_cover')
    call_open_cover = async_mock_service(hass, DOMAIN, 'open_cover')

    await hass.async_add_job(acc.char_target_position.client_update_value, 25)
    await hass.async_block_till_done()
    assert call_close_cover
    assert call_close_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2

    await hass.async_add_job(acc.char_target_position.client_update_value, 90)
    await hass.async_block_till_done()
    assert call_open_cover[0]
    assert call_open_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 100
    assert acc.char_target_position.value == 100
    assert acc.char_position_state.value == 2

    await hass.async_add_job(acc.char_target_position.client_update_value, 55)
    await hass.async_block_till_done()
    assert call_open_cover[1]
    assert call_open_cover[1].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 100
    assert acc.char_target_position.value == 100
    assert acc.char_position_state.value == 2


async def test_window_open_close_stop(hass, cls):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'cover.window'

    hass.states.async_set(entity_id, STATE_UNKNOWN,
                          {ATTR_SUPPORTED_FEATURES: SUPPORT_STOP})
    acc = cls.window_basic(hass, 'Cover', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    # Set from HomeKit
    call_close_cover = async_mock_service(hass, DOMAIN, 'close_cover')
    call_open_cover = async_mock_service(hass, DOMAIN, 'open_cover')
    call_stop_cover = async_mock_service(hass, DOMAIN, 'stop_cover')

    await hass.async_add_job(acc.char_target_position.client_update_value, 25)
    await hass.async_block_till_done()
    assert call_close_cover
    assert call_close_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2

    await hass.async_add_job(acc.char_target_position.client_update_value, 90)
    await hass.async_block_till_done()
    assert call_open_cover
    assert call_open_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 100
    assert acc.char_target_position.value == 100
    assert acc.char_position_state.value == 2

    await hass.async_add_job(acc.char_target_position.client_update_value, 55)
    await hass.async_block_till_done()
    assert call_stop_cover
    assert call_stop_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 50
    assert acc.char_position_state.value == 2
