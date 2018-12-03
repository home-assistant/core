"""The tests for the Restore component."""
from datetime import datetime

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CoreState, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import (
    RestoreStateData, RestoreEntity, StoredState, DATA_RESTORE_STATE_TASK)
from homeassistant.util import dt as dt_util

from asynctest import patch

from tests.common import mock_coro


async def test_caching_data(hass):
    """Test that we cache data."""
    now = dt_util.utcnow()
    stored_states = [
        StoredState(State('input_boolean.b0', 'on'), now),
        StoredState(State('input_boolean.b1', 'on'), now),
        StoredState(State('input_boolean.b2', 'on'), now),
    ]

    data = await RestoreStateData.async_get_instance(hass)
    await data.store.async_save([state.as_dict() for state in stored_states])

    # Emulate a fresh load
    hass.data[DATA_RESTORE_STATE_TASK] = None

    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = 'input_boolean.b1'

    # Mock that only b1 is present this run
    with patch('homeassistant.helpers.restore_state.Store.async_save'
               ) as mock_write_data:
        state = await entity.async_get_last_state()

    assert state is not None
    assert state.entity_id == 'input_boolean.b1'
    assert state.state == 'on'

    assert mock_write_data.called


async def test_hass_starting(hass):
    """Test that we cache data."""
    hass.state = CoreState.starting

    now = dt_util.utcnow()
    stored_states = [
        StoredState(State('input_boolean.b0', 'on'), now),
        StoredState(State('input_boolean.b1', 'on'), now),
        StoredState(State('input_boolean.b2', 'on'), now),
    ]

    data = await RestoreStateData.async_get_instance(hass)
    await data.store.async_save([state.as_dict() for state in stored_states])

    # Emulate a fresh load
    hass.data[DATA_RESTORE_STATE_TASK] = None

    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = 'input_boolean.b1'

    # Mock that only b1 is present this run
    states = [
        State('input_boolean.b1', 'on'),
    ]
    with patch('homeassistant.helpers.restore_state.Store.async_save'
               ) as mock_write_data, patch.object(
                   hass.states, 'async_all', return_value=states):
        state = await entity.async_get_last_state()

    assert state is not None
    assert state.entity_id == 'input_boolean.b1'
    assert state.state == 'on'

    # Assert that no data was written yet, since hass is still starting.
    assert not mock_write_data.called

    # Finish hass startup
    with patch('homeassistant.helpers.restore_state.Store.async_save'
               ) as mock_write_data:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    # Assert that this session states were written
    assert mock_write_data.called


async def test_dump_data(hass):
    """Test that we cache data."""
    states = [
        State('input_boolean.b0', 'on'),
        State('input_boolean.b1', 'on'),
        State('input_boolean.b2', 'on'),
    ]

    entity = Entity()
    entity.hass = hass
    entity.entity_id = 'input_boolean.b0'
    await entity.async_added_to_hass()

    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = 'input_boolean.b1'
    await entity.async_added_to_hass()

    data = await RestoreStateData.async_get_instance(hass)
    now = dt_util.utcnow()
    data.last_states = {
        'input_boolean.b0': StoredState(State('input_boolean.b0', 'off'), now),
        'input_boolean.b1': StoredState(State('input_boolean.b1', 'off'), now),
        'input_boolean.b2': StoredState(State('input_boolean.b2', 'off'), now),
        'input_boolean.b3': StoredState(State('input_boolean.b3', 'off'), now),
        'input_boolean.b4': StoredState(
            State('input_boolean.b4', 'off'),
            datetime(1985, 10, 26, 1, 22, tzinfo=dt_util.UTC)),
    }

    with patch('homeassistant.helpers.restore_state.Store.async_save'
               ) as mock_write_data, patch.object(
                   hass.states, 'async_all', return_value=states):
        await data.async_dump_states()

    assert mock_write_data.called
    args = mock_write_data.mock_calls[0][1]
    written_states = args[0]

    # b0 should not be written, since it didn't extend RestoreEntity
    # b1 should be written, since it is present in the current run
    # b2 should not be written, since it is not registered with the helper
    # b3 should be written, since it is still not expired
    # b4 should not be written, since it is now expired
    assert len(written_states) == 2
    assert written_states[0]['state']['entity_id'] == 'input_boolean.b1'
    assert written_states[0]['state']['state'] == 'on'
    assert written_states[1]['state']['entity_id'] == 'input_boolean.b3'
    assert written_states[1]['state']['state'] == 'off'

    # Test that removed entities are not persisted
    await entity.async_will_remove_from_hass()

    with patch('homeassistant.helpers.restore_state.Store.async_save'
               ) as mock_write_data, patch.object(
                   hass.states, 'async_all', return_value=states):
        await data.async_dump_states()

    assert mock_write_data.called
    args = mock_write_data.mock_calls[0][1]
    written_states = args[0]
    assert len(written_states) == 1
    assert written_states[0]['state']['entity_id'] == 'input_boolean.b3'
    assert written_states[0]['state']['state'] == 'off'


async def test_dump_error(hass):
    """Test that we cache data."""
    states = [
        State('input_boolean.b0', 'on'),
        State('input_boolean.b1', 'on'),
        State('input_boolean.b2', 'on'),
    ]

    entity = Entity()
    entity.hass = hass
    entity.entity_id = 'input_boolean.b0'
    await entity.async_added_to_hass()

    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = 'input_boolean.b1'
    await entity.async_added_to_hass()

    data = await RestoreStateData.async_get_instance(hass)

    with patch('homeassistant.helpers.restore_state.Store.async_save',
               return_value=mock_coro(exception=HomeAssistantError)
               ) as mock_write_data, patch.object(
                   hass.states, 'async_all', return_value=states):
        await data.async_dump_states()

    assert mock_write_data.called


async def test_load_error(hass):
    """Test that we cache data."""
    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = 'input_boolean.b1'

    with patch('homeassistant.helpers.storage.Store.async_load',
               return_value=mock_coro(exception=HomeAssistantError)):
        state = await entity.async_get_last_state()

    assert state is None


async def test_state_saved_on_remove(hass):
    """Test that we save entity state on removal."""
    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = 'input_boolean.b0'
    await entity.async_added_to_hass()

    hass.states.async_set('input_boolean.b0', 'on')

    data = await RestoreStateData.async_get_instance(hass)

    # No last states should currently be saved
    assert not data.last_states

    await entity.async_will_remove_from_hass()

    # We should store the input boolean state when it is removed
    assert data.last_states['input_boolean.b0'].state.state == 'on'
