"""The tests for the Restore component."""
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CoreState, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import (
    RestoreStateData, RestoreEntity, DATA_RESTORE_STATE_TASK)

from asynctest import patch

from tests.common import mock_coro


async def test_caching_data(hass):
    """Test that we cache data."""
    states = [
        State('input_boolean.b0', 'on'),
        State('input_boolean.b1', 'on'),
        State('input_boolean.b2', 'on'),
    ]

    data = await RestoreStateData.async_get_instance(hass)
    await data.store.async_save([state.as_dict() for state in states])

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

    states = [
        State('input_boolean.b0', 'on'),
        State('input_boolean.b1', 'on'),
        State('input_boolean.b2', 'on'),
    ]

    data = await RestoreStateData.async_get_instance(hass)
    await data.store.async_save([state.as_dict() for state in states])

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

    with patch('homeassistant.helpers.restore_state.Store.async_save'
               ) as mock_write_data, patch.object(
                   hass.states, 'async_all', return_value=states):
        await data.async_dump_states()

    assert mock_write_data.called
    args = mock_write_data.mock_calls[0][1]
    written_states = args[0]

    # Assert that only input_boolean.b1 was written, since it was the only
    # state linked to a RestoreEntity
    assert len(written_states) == 1
    assert written_states[0]['entity_id'] == 'input_boolean.b1'
    assert written_states[0]['state'] == 'on'

    # Test that removed entities are not persisted
    await entity.async_will_remove_from_hass()

    with patch('homeassistant.helpers.restore_state.Store.async_save'
               ) as mock_write_data, patch.object(
                   hass.states, 'async_all', return_value=states):
        await data.async_dump_states()

    assert mock_write_data.called
    args = mock_write_data.mock_calls[0][1]
    written_states = args[0]
    assert not written_states


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
