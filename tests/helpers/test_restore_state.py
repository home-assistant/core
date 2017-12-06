"""The tests for the Restore component."""
import asyncio
from datetime import timedelta
from unittest.mock import patch, MagicMock

from homeassistant.setup import setup_component
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CoreState, split_entity_id, State
import homeassistant.util.dt as dt_util
from homeassistant.components import input_boolean, recorder
from homeassistant.helpers.restore_state import (
    async_get_last_state, DATA_RESTORE_CACHE)
from homeassistant.components.recorder.models import RecorderRuns, States

from tests.common import (
    get_test_home_assistant, mock_coro, init_recorder_component,
    mock_component)


@asyncio.coroutine
def test_caching_data(hass):
    """Test that we cache data."""
    mock_component(hass, 'recorder')
    hass.state = CoreState.starting

    states = [
        State('input_boolean.b0', 'on'),
        State('input_boolean.b1', 'on'),
        State('input_boolean.b2', 'on'),
    ]

    with patch('homeassistant.helpers.restore_state.last_recorder_run',
               return_value=MagicMock(end=dt_util.utcnow())), \
            patch('homeassistant.helpers.restore_state.get_states',
                  return_value=states), \
            patch('homeassistant.helpers.restore_state.wait_connection_ready',
                  return_value=mock_coro(True)):
        state = yield from async_get_last_state(hass, 'input_boolean.b1')

    assert DATA_RESTORE_CACHE in hass.data
    assert hass.data[DATA_RESTORE_CACHE] == {st.entity_id: st for st in states}

    assert state is not None
    assert state.entity_id == 'input_boolean.b1'
    assert state.state == 'on'

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    yield from hass.async_block_till_done()

    assert DATA_RESTORE_CACHE not in hass.data


@asyncio.coroutine
def test_hass_running(hass):
    """Test that cache cannot be accessed while hass is running."""
    mock_component(hass, 'recorder')

    states = [
        State('input_boolean.b0', 'on'),
        State('input_boolean.b1', 'on'),
        State('input_boolean.b2', 'on'),
    ]

    with patch('homeassistant.helpers.restore_state.last_recorder_run',
               return_value=MagicMock(end=dt_util.utcnow())), \
            patch('homeassistant.helpers.restore_state.get_states',
                  return_value=states), \
            patch('homeassistant.helpers.restore_state.wait_connection_ready',
                  return_value=mock_coro(True)):
        state = yield from async_get_last_state(hass, 'input_boolean.b1')
    assert state is None


@asyncio.coroutine
def test_not_connected(hass):
    """Test that cache cannot be accessed if db connection times out."""
    mock_component(hass, 'recorder')
    hass.state = CoreState.starting

    states = [State('input_boolean.b1', 'on')]

    with patch('homeassistant.helpers.restore_state.last_recorder_run',
               return_value=MagicMock(end=dt_util.utcnow())), \
            patch('homeassistant.helpers.restore_state.get_states',
                  return_value=states), \
            patch('homeassistant.helpers.restore_state.wait_connection_ready',
                  return_value=mock_coro(False)):
        state = yield from async_get_last_state(hass, 'input_boolean.b1')
    assert state is None


@asyncio.coroutine
def test_no_last_run_found(hass):
    """Test that cache cannot be accessed if no last run found."""
    mock_component(hass, 'recorder')
    hass.state = CoreState.starting

    states = [State('input_boolean.b1', 'on')]

    with patch('homeassistant.helpers.restore_state.last_recorder_run',
               return_value=None), \
            patch('homeassistant.helpers.restore_state.get_states',
                  return_value=states), \
            patch('homeassistant.helpers.restore_state.wait_connection_ready',
                  return_value=mock_coro(True)):
        state = yield from async_get_last_state(hass, 'input_boolean.b1')
    assert state is None


@asyncio.coroutine
def test_cache_timeout(hass):
    """Test that cache timeout returns none."""
    mock_component(hass, 'recorder')
    hass.state = CoreState.starting

    states = [State('input_boolean.b1', 'on')]

    @asyncio.coroutine
    def timeout_coro():
        raise asyncio.TimeoutError()

    with patch('homeassistant.helpers.restore_state.last_recorder_run',
               return_value=MagicMock(end=dt_util.utcnow())), \
            patch('homeassistant.helpers.restore_state.get_states',
                  return_value=states), \
            patch('homeassistant.helpers.restore_state.wait_connection_ready',
                  return_value=timeout_coro()):
        state = yield from async_get_last_state(hass, 'input_boolean.b1')
    assert state is None


def _add_data_in_last_run(hass, entities):
    """Add test data in the last recorder_run."""
    # pylint: disable=protected-access
    t_now = dt_util.utcnow() - timedelta(minutes=10)
    t_min_1 = t_now - timedelta(minutes=20)
    t_min_2 = t_now - timedelta(minutes=30)

    with recorder.session_scope(hass=hass) as session:
        session.add(RecorderRuns(
            start=t_min_2,
            end=t_now,
            created=t_min_2
        ))

        for entity_id, state in entities.items():
            session.add(States(
                entity_id=entity_id,
                domain=split_entity_id(entity_id)[0],
                state=state,
                attributes='{}',
                last_changed=t_min_1,
                last_updated=t_min_1,
                created=t_min_1))


def test_filling_the_cache():
    """Test filling the cache from the DB."""
    test_entity_id1 = 'input_boolean.b1'
    test_entity_id2 = 'input_boolean.b2'

    hass = get_test_home_assistant()
    hass.state = CoreState.starting

    init_recorder_component(hass)

    _add_data_in_last_run(hass, {
        test_entity_id1: 'on',
        test_entity_id2: 'off',
    })

    hass.block_till_done()
    setup_component(hass, input_boolean.DOMAIN, {
        input_boolean.DOMAIN: {
            'b1': None,
            'b2': None,
        }})

    hass.start()

    state = hass.states.get('input_boolean.b1')
    assert state
    assert state.state == 'on'

    state = hass.states.get('input_boolean.b2')
    assert state
    assert state.state == 'off'

    hass.stop()
